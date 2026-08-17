"""SOW generation: LLM estimation, contingency, and Celery-backed async runs."""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.activity_event import ActivityActor
from app.models.project_technology import ProjectTechnology
from app.models.requirement import Requirement, RequirementCategory, RequirementPriority, RequirementStatus
from app.models.sow_document import SowDocument, SowGenerationStatus, SowStatus
from app.services.execution import record_activity
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements

logger = logging.getLogger(__name__)

CONTINGENCY_RATE = Decimal("0.15")
AMBIGUOUS_CATEGORIES = {RequirementCategory.ASSUMPTION, RequirementCategory.RISK}
AMBIGUOUS_PRIORITIES = {RequirementPriority.UNKNOWN}


class SowTierLLM(BaseModel):
    tier_key: str = Field(description="Stable key like mvp, recommended, full_scope")
    tier_name: str
    description: str = ""
    total_hours: float = Field(ge=0)
    requirement_ids: list[str] = Field(default_factory=list)
    estimated_weeks: int = Field(ge=1, default=4)


class SowLaborModule(BaseModel):
    module_name: str
    frontend_hours: float = Field(ge=0, default=0)
    backend_hours: float = Field(ge=0, default=0)
    devops_hours: float = Field(ge=0, default=0)
    qa_hours: float = Field(ge=0, default=0)
    requirement_ids: list[str] = Field(default_factory=list)


class SowLLMResult(BaseModel):
    summary: str = ""
    out_of_scope_guardrails: list[str] = Field(default_factory=list)
    tiers: list[SowTierLLM] = Field(default_factory=list)
    labor_modules: list[SowLaborModule] = Field(default_factory=list)


def _format_requirements_for_prompt(requirements: list[Requirement]) -> str:
    lines: list[str] = []
    for req in requirements:
        lines.append(
            f"- {req.stable_id}: {req.title} "
            f"[{req.category.value}, {req.priority.value}, {req.status.value}] "
            f"{(req.description or '')[:400]}"
        )
        if req.acceptance_criteria:
            for ac in req.acceptance_criteria[:4]:
                lines.append(f"    AC: {ac}")
    return "\n".join(lines) if lines else "No requirements."


async def _format_stack_for_prompt(db: AsyncSession, project_id: UUID) -> str:
    result = await db.execute(
        select(ProjectTechnology)
        .where(ProjectTechnology.project_id == project_id)
        .order_by(ProjectTechnology.sort_order.asc(), ProjectTechnology.created_at.asc())
    )
    rows = result.scalars().all()
    if not rows:
        return "No technology stack selected yet."
    lines = []
    for row in rows:
        rationale = (row.rationale or "").strip()
        suffix = f" — {rationale[:200]}" if rationale else ""
        lines.append(f"- {row.catalog_id} ({row.category.value}){suffix}")
    return "\n".join(lines)


def _requirement_ambiguity_map(requirements: list[Requirement]) -> dict[str, bool]:
    return {
        req.stable_id: (
            req.category in AMBIGUOUS_CATEGORIES
            or req.priority in AMBIGUOUS_PRIORITIES
        )
        for req in requirements
    }


def _tier_has_ambiguity(tier: SowTierLLM, ambiguity: dict[str, bool]) -> bool:
    for stable_id in tier.requirement_ids:
        if ambiguity.get(stable_id):
            return True
    return False


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _compute_tier_cost(total_hours: float, hourly_rate: Decimal) -> Decimal:
    hours = Decimal(str(total_hours))
    return _quantize_money(hours * hourly_rate)


def apply_contingency_to_tiers(
    tiers: list[SowTierLLM],
    requirements: list[Requirement],
) -> list[dict[str, Any]]:
    """Apply 15% hour buffer when a tier includes ambiguous requirements."""
    ambiguity = _requirement_ambiguity_map(requirements)
    payload: list[dict[str, Any]] = []
    for tier in tiers:
        hours = Decimal(str(tier.total_hours))
        if _tier_has_ambiguity(tier, ambiguity):
            hours = hours * (Decimal("1") + CONTINGENCY_RATE)
        adjusted_hours = float(hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        payload.append(
            {
                "tier_key": tier.tier_key,
                "tier_name": tier.tier_name,
                "description": tier.description,
                "total_hours": adjusted_hours,
                "requirement_ids": tier.requirement_ids,
                "estimated_weeks": tier.estimated_weeks,
                "contingency_applied": _tier_has_ambiguity(tier, ambiguity),
            }
        )
    return payload


def build_tier_payloads_with_costs(
    tier_dicts: list[dict[str, Any]],
    hourly_rate: Decimal,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tier in tier_dicts:
        total_cost = _compute_tier_cost(tier["total_hours"], hourly_rate)
        out.append(
            {
                **tier,
                "total_cost": float(total_cost),
            }
        )
    return out


def build_labor_breakdown_payload(modules: list[SowLaborModule]) -> list[dict[str, Any]]:
    return [module.model_dump() for module in modules]


async def _select_source_requirements(
    db: AsyncSession,
    project_id: UUID,
) -> list[Requirement]:
    requirements, _open = await list_working_requirements(db, project_id)
    usable = [
        req
        for req in requirements
        if req.status in (RequirementStatus.CONFIRMED, RequirementStatus.PROPOSED)
    ]
    confirmed = [req for req in usable if req.status == RequirementStatus.CONFIRMED]
    if not confirmed and not usable:
        raise HTTPException(
            status_code=400,
            detail="Confirm at least one requirement before generating a SOW.",
        )
    return confirmed if confirmed else usable


async def generate_sow_llm_result(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    hourly_rate: Decimal,
) -> tuple[SowLLMResult, list[Requirement]]:
    await get_project_or_404(project_id, user_id, db)
    source_reqs = await _select_source_requirements(db, project_id)
    requirements_json = _format_requirements_for_prompt(source_reqs)
    stack_json = await _format_stack_for_prompt(db, project_id)

    prompt = PromptTemplate.from_template(
        """You are a Principal Software Architect and Agency Sales Director.
Your job is to convert extracted technical requirements into a professional
Statement of Work (SOW) and multi-tier pricing estimation.

INPUT DATA:
- Confirmed Requirements:
{confirmed_requirements_json}
- Tech Stack:
{recommended_stack_json}
- Hourly Rate: ${hourly_rate}/hr

TASKS:
1. Group requirements into functional modules (e.g., Auth, Backend API, Dashboard).
2. Estimate realistic labor hours per module split into: Frontend, Backend, DevOps/Infra, QA/Testing.
3. Apply planning judgment for ambiguous items (a 15% contingency may be applied in code later).
4. Construct 3 tiers:
   - "mvp": Mandatory core requirements only.
   - "recommended": Core + high-value secondary features + basic optimizations.
   - "full_scope": All extracted requirements + advanced polish + launch monitoring.
5. Identify explicit "Out of Scope" items (e.g., third-party API fees, post-handoff maintenance).

Use requirement stable IDs (REQ-001, etc.) in tier requirement_ids.
Do not invent requirements that are not in the input list.
total_hours should reflect labor only (not contingency).
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(SowLLMResult)

    try:
        result: SowLLMResult = await (prompt | model).ainvoke(
            {
                "confirmed_requirements_json": requirements_json,
                "recommended_stack_json": stack_json,
                "hourly_rate": f"{hourly_rate:.2f}",
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate SOW")

    if not result.tiers:
        raise HTTPException(
            status_code=400,
            detail="The model returned an empty SOW. Try again after refining requirements.",
        )

    return result, source_reqs


def generate_sow_token() -> str:
    return secrets.token_urlsafe(32)


async def run_sow_generation(
    sow_document_id: str,
    user_id: str,
    project_id: str,
) -> None:
    """Celery entrypoint: generate SOW content and persist on sow_documents row."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            sow_id = UUID(sow_document_id)
            uid = UUID(user_id)
            pid = UUID(project_id)

            sow = await db.get(SowDocument, sow_id)
            if sow is None or sow.project_id != pid:
                logger.error("SOW %s not found for project %s", sow_document_id, project_id)
                return

            sow.generation_status = SowGenerationStatus.RUNNING
            await db.commit()

            hourly_rate = Decimal(str(sow.hourly_rate))

            try:
                llm_result, source_reqs = await generate_sow_llm_result(
                    db, uid, pid, hourly_rate
                )
                tier_dicts = apply_contingency_to_tiers(llm_result.tiers, source_reqs)
                tiers_with_cost = build_tier_payloads_with_costs(tier_dicts, hourly_rate)

                sow.summary = llm_result.summary.strip() or None
                sow.out_of_scope_items = llm_result.out_of_scope_guardrails or []
                sow.tiers = tiers_with_cost
                sow.labor_breakdown = build_labor_breakdown_payload(
                    llm_result.labor_modules
                )
                sow.generation_status = SowGenerationStatus.COMPLETE
                if sow.status == SowStatus.ACCEPTED:
                    sow.status = SowStatus.DRAFT

                await record_activity(
                    db,
                    pid,
                    summary="AI generated Statement of Work tiers",
                    event_type="sow.generated",
                    actor=ActivityActor.AI,
                    entity_type="sow_document",
                    entity_id=sow.id,
                    payload={"tier_count": len(tiers_with_cost)},
                )
                await db.commit()
                logger.info("SOW %s generation complete", sow_document_id)
            except Exception as e:
                logger.error(
                    "SOW %s generation failed: %s",
                    sow_document_id,
                    e,
                    exc_info=True,
                )
                sow.generation_status = SowGenerationStatus.FAILED
                await db.commit()
                raise
    finally:
        await engine.dispose()


async def mark_sow_generation_failed(sow_document_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            sow = await db.get(SowDocument, UUID(sow_document_id))
            if sow is not None:
                sow.generation_status = SowGenerationStatus.FAILED
                await db.commit()
    finally:
        await engine.dispose()
