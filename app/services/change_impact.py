import json
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.change_request import (
    ChangeRequest,
    ChangeRequestStatus,
    ImpactVerdict,
)
from app.models.requirement_baseline import BaselineStatus, RequirementBaseline
from app.schemas.change_request import ChangeImpactAnalysisBody, ChangeRequestResponse
from app.services.project_access import get_project_or_404
from app.services.qa_chain import format_chunks_into_text
from app.services.requirements_extractor import get_current_baseline
from app.services.retrieval import hybrid_search

logger = logging.getLogger(__name__)


class LLMChangeImpactResult(BaseModel):
    verdict: str = Field(
        description=(
            "One of: covered_by_baseline, likely_change_request, "
            "conflicts_with_baseline, new_capability, unclear_needs_clarification"
        )
    )
    confidence: str = Field(description="high, medium, or low")
    summary: str
    affected_requirement_ids: list[str] = Field(default_factory=list)
    mvp_impact: str | None = None
    risks: list[str] = Field(default_factory=list)
    client_questions: list[str] = Field(default_factory=list)
    suggested_response: str | None = None
    source_citation_indexes: list[int] = Field(default_factory=list)


def _format_baseline(snapshot: list[dict[str, Any]]) -> str:
    lines = []
    for item in snapshot:
        lines.append(
            f"- {item.get('stable_id')}: {item.get('title')} "
            f"({item.get('category')}, {item.get('priority')}) — "
            f"{item.get('description', '')}"
        )
    return "\n".join(lines)


def _chunk_to_source(chunk) -> dict[str, Any]:
    return {
        "document_id": str(chunk.doc_id),
        "chunk_id": str(chunk.id),
        "page": (chunk.page_num or 0) + 1,
        "excerpt": (chunk.content or "")[:300],
    }


def _analysis_from_row(
    change: ChangeRequest,
) -> ChangeImpactAnalysisBody | None:
    if not change.analysis:
        return None
    return ChangeImpactAnalysisBody.model_validate(change.analysis)


def change_request_to_response(change: ChangeRequest) -> ChangeRequestResponse:
    return ChangeRequestResponse(
        id=change.id,
        project_id=change.project_id,
        baseline_id=change.baseline_id,
        request_text=change.request_text,
        status=change.status,
        analysis=_analysis_from_row(change),
        created_at=change.created_at,
        updated_at=change.updated_at,
    )


async def analyze_change_request(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    request_text: str,
) -> ChangeRequestResponse:
    await get_project_or_404(project_id, user_id, db)

    baseline_resp = await get_current_baseline(db, user_id, project_id)
    if baseline_resp is None:
        raise HTTPException(
            status_code=400,
            detail="Approve a baseline before analyzing change requests.",
        )

    baseline = await db.get(RequirementBaseline, baseline_resp.id)
    if baseline is None:
        raise HTTPException(status_code=404, detail="Baseline not found")

    chunks = await hybrid_search(
        question=request_text,
        db=db,
        user_id=user_id,
        project_id=project_id,
        k=8,
    )
    context = format_chunks_into_text(chunks) if chunks else "No matching document excerpts."
    baseline_text = _format_baseline(baseline.snapshot)

    prompt = PromptTemplate.from_template(
        """You are helping a freelance developer or indie builder evaluate a new
client request or product idea against an approved project baseline.

Be careful and evidence-based. Do NOT claim something is legally "out of scope".
Use verdicts:
- covered_by_baseline: clearly already in approved baseline
- likely_change_request: adds scope beyond baseline, needs separate quote/clarification
- conflicts_with_baseline: contradicts an approved requirement
- new_capability: genuinely new capability not in baseline
- unclear_needs_clarification: not enough information

Reference baseline stable IDs (REQ-001, etc.) in affected_requirement_ids.
Cite document context using [1], [2] indexes.

Approved baseline:
{baseline}

Document context:
{context}

New request or idea:
{request}
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(LLMChangeImpactResult)

    try:
        result: LLMChangeImpactResult = (prompt | model).invoke(
            {
                "baseline": baseline_text,
                "context": context,
                "request": request_text,
            }
        )
    except Exception as e:
        logger.error(f"Change impact analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to analyze change request") from e

    try:
        verdict = ImpactVerdict(result.verdict)
    except ValueError:
        verdict = ImpactVerdict.UNCLEAR

    sources = []
    for idx in result.source_citation_indexes:
        if chunks and 1 <= idx <= len(chunks):
            sources.append(_chunk_to_source(chunks[idx - 1]))

    analysis = ChangeImpactAnalysisBody(
        verdict=verdict,
        confidence=result.confidence if result.confidence in ("high", "medium", "low") else "medium",  # type: ignore[arg-type]
        summary=result.summary,
        affected_requirement_ids=result.affected_requirement_ids,
        mvp_impact=result.mvp_impact,
        risks=result.risks,
        client_questions=result.client_questions,
        suggested_response=result.suggested_response,
        sources=sources,
    )

    change = ChangeRequest(
        project_id=project_id,
        baseline_id=baseline.id,
        request_text=request_text,
        status=ChangeRequestStatus.ANALYZED,
        analysis=json.loads(analysis.model_dump_json()),
    )
    db.add(change)
    await db.commit()
    await db.refresh(change)
    return change_request_to_response(change)


async def list_change_requests(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> list[ChangeRequestResponse]:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(ChangeRequest)
        .where(ChangeRequest.project_id == project_id)
        .order_by(ChangeRequest.created_at.desc())
    )
    return [change_request_to_response(c) for c in result.scalars().all()]
