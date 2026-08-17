"""AI evaluation of client scope change requests."""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.requirement import Requirement, RequirementStatus
from app.services.llm_errors import raise_llm_http_error
from app.services.qa_chain import format_chunks_into_text
from app.services.requirements import list_working_requirements
from app.services.retrieval import hybrid_search
from app.services.sow_service import get_latest_sow

logger = logging.getLogger(__name__)


class ScopeChangeEvaluation(BaseModel):
    is_out_of_scope: bool = Field(
        description="True if the request is outside the agreed project scope"
    )
    reasoning: str = Field(description="Brief explanation for the agency team")
    estimated_hours: float = Field(
        ge=0,
        description="Estimated additional engineering hours if out of scope",
    )


def _format_confirmed_requirements(requirements: list[Requirement]) -> str:
    confirmed = [r for r in requirements if r.status == RequirementStatus.CONFIRMED]
    if not confirmed:
        return "No confirmed requirements on record."
    lines = []
    for req in confirmed:
        lines.append(
            f"- {req.stable_id}: {req.title} — {(req.description or '')[:300]}"
        )
    return "\n".join(lines)


async def evaluate_scope_change(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    client_description: str,
) -> tuple[ScopeChangeEvaluation, Decimal | None, Decimal | None]:
    """Run hybrid retrieval + LLM variance check against confirmed scope."""
    requirements, _ = await list_working_requirements(db, project_id)
    confirmed_text = _format_confirmed_requirements(requirements)

    sow = await get_latest_sow(db, project_id)
    out_of_scope_items: list[str] = []
    hourly_rate = Decimal("100.00")
    if sow is not None:
        hourly_rate = Decimal(str(sow.hourly_rate))
        out_of_scope_items = list(sow.out_of_scope_items or [])

    chunks = await hybrid_search(
        question=client_description,
        db=db,
        user_id=user_id,
        project_id=project_id,
        k=8,
    )
    context = format_chunks_into_text(chunks) if chunks else "No matching document passages."

    out_of_scope_text = (
        "\n".join(f"- {item}" for item in out_of_scope_items)
        if out_of_scope_items
        else "None listed."
    )

    prompt = PromptTemplate.from_template(
        """You are a senior agency delivery lead evaluating a client feature request.

Confirmed in-scope requirements:
{confirmed_requirements}

Explicitly out-of-scope guardrails from the SOW:
{out_of_scope_guardrails}

Relevant document passages:
{document_context}

Client request:
{client_description}

Determine if this request is OUT OF SCOPE relative to confirmed requirements and SOW guardrails.
If clearly covered by an existing confirmed requirement, mark in-scope (is_out_of_scope=false).
If it expands scope, adds new capability, or contradicts out-of-scope guardrails, mark out-of-scope.

For out-of-scope requests, estimate realistic additional engineering hours (0 if in-scope).
Be conservative and practical for a small dev agency."""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(ScopeChangeEvaluation)

    try:
        result: ScopeChangeEvaluation = await (prompt | model).ainvoke(
            {
                "confirmed_requirements": confirmed_text,
                "out_of_scope_guardrails": out_of_scope_text,
                "document_context": context,
                "client_description": client_description.strip(),
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="evaluate scope change")

    estimated_cost: Decimal | None = None
    estimated_hours: Decimal | None = None
    if result.is_out_of_scope and result.estimated_hours > 0:
        estimated_hours = Decimal(str(result.estimated_hours)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        estimated_cost = (estimated_hours * hourly_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return result, estimated_hours, estimated_cost
