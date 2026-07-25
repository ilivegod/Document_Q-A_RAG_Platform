import json
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, Document_Status
from app.models.technology_exploration import (
    TechnologyExploration,
    TechnologyExplorationStatus,
)
from app.schemas.technology import (
    TechnologyAlternative,
    TechnologyAnalysisBody,
    TechnologyExplorationResponse,
    TechnologyResource,
)
from app.services.project_access import get_project_or_404
from app.services.qa_chain import format_chunks_into_text
from app.services.requirements import list_working_requirements
from app.services.requirements_extractor import get_current_baseline
from app.services.retrieval import hybrid_search

logger = logging.getLogger(__name__)


class LLMTechnologyResult(BaseModel):
    recommended: str
    confidence: str = Field(description="high, medium, or low")
    summary: str
    alternatives: list[TechnologyAlternative] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    resources: list[TechnologyResource] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    requirements_addressed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    source_citation_indexes: list[int] = Field(default_factory=list)


def _chunk_to_source(chunk) -> dict[str, Any]:
    return {
        "document_id": str(chunk.doc_id),
        "chunk_id": str(chunk.id),
        "page": (chunk.page_num or 0) + 1,
        "excerpt": (chunk.content or "")[:300],
    }


def _format_requirements(requirements) -> str:
    if not requirements:
        return "No structured requirements yet."
    lines = []
    for req in requirements:
        lines.append(
            f"- {req.stable_id}: {req.title} "
            f"({req.category.value}, {req.priority.value}) — "
            f"{req.description or ''}"
        )
    return "\n".join(lines)


def exploration_to_response(
    row: TechnologyExploration,
) -> TechnologyExplorationResponse:
    return TechnologyExplorationResponse(
        id=row.id,
        project_id=row.project_id,
        topic=row.topic,
        status=row.status,
        analysis=TechnologyAnalysisBody.model_validate(row.analysis),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _project_has_explore_context(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> bool:
    requirements, _ = await list_working_requirements(db, project_id)
    if requirements:
        return True
    result = await db.execute(
        select(func.count())
        .select_from(Document)
        .where(
            Document.project_id == project_id,
            Document.user_id == user_id,
            Document.status == Document_Status.READY,
        )
    )
    return int(result.scalar_one()) > 0


async def explore_technology(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    topic: str,
) -> TechnologyExplorationResponse:
    await get_project_or_404(project_id, user_id, db)

    if not await _project_has_explore_context(db, project_id, user_id):
        raise HTTPException(
            status_code=400,
            detail=(
                "Upload documents or extract requirements before exploring "
                "technology options."
            ),
        )

    requirements, open_questions = await list_working_requirements(db, project_id)
    requirements_text = _format_requirements(requirements)
    if open_questions:
        questions_text = "\n".join(
            f"- {q.stable_id}: {q.title}" for q in open_questions
        )
        requirements_text += f"\n\nOpen questions:\n{questions_text}"

    baseline_text = "No approved baseline."
    baseline_resp = await get_current_baseline(db, user_id, project_id)
    if baseline_resp and baseline_resp.snapshot:
        baseline_text = "\n".join(
            f"- {item.get('stable_id')}: {item.get('title')}"
            for item in baseline_resp.snapshot
        )

    chunks = await hybrid_search(
        question=topic,
        db=db,
        user_id=user_id,
        project_id=project_id,
        k=8,
    )
    context = (
        format_chunks_into_text(chunks)
        if chunks
        else "No matching document excerpts."
    )

    prompt = PromptTemplate.from_template(
        """You are a senior technical advisor helping a freelance developer or
indie builder choose technologies for a specific project.

Ground recommendations in the project requirements and document context below.
Provide 2-4 credible alternatives when comparing stacks or tools.
Include official documentation URLs in resources when you know them.
State assumptions clearly. Reference requirement stable IDs (REQ-001, etc.).
Cite document context using [1], [2] indexes in source_citation_indexes.

Do NOT recommend blindly — explain trade-offs for THIS project.

Project requirements:
{requirements}

Approved baseline (if any):
{baseline}

Document context:
{context}

Technology question or comparison:
{topic}
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(LLMTechnologyResult)

    try:
        result: LLMTechnologyResult = (prompt | model).invoke(
            {
                "requirements": requirements_text,
                "baseline": baseline_text,
                "context": context,
                "topic": topic,
            }
        )
    except Exception as e:
        logger.error(f"Technology exploration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Failed to explore technology options",
        ) from e

    sources = []
    for idx in result.source_citation_indexes:
        if chunks and 1 <= idx <= len(chunks):
            sources.append(_chunk_to_source(chunks[idx - 1]))

    confidence = (
        result.confidence
        if result.confidence in ("high", "medium", "low")
        else "medium"
    )

    analysis = TechnologyAnalysisBody(
        recommended=result.recommended,
        confidence=confidence,  # type: ignore[arg-type]
        summary=result.summary,
        alternatives=result.alternatives,
        trade_offs=result.trade_offs,
        resources=result.resources,
        assumptions=result.assumptions,
        requirements_addressed=result.requirements_addressed,
        risks=result.risks,
        clarifying_questions=result.clarifying_questions,
        sources=sources,
    )

    row = TechnologyExploration(
        project_id=project_id,
        topic=topic,
        status=TechnologyExplorationStatus.COMPLETED,
        analysis=json.loads(analysis.model_dump_json()),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return exploration_to_response(row)


async def list_technology_explorations(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> list[TechnologyExplorationResponse]:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(TechnologyExploration)
        .where(TechnologyExploration.project_id == project_id)
        .order_by(TechnologyExploration.created_at.desc())
    )
    return [exploration_to_response(row) for row in result.scalars().all()]
