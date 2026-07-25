import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, Document_Status
from app.models.requirement import Requirement, RequirementCategory, RequirementStatus
from app.models.requirement_baseline import BaselineStatus, RequirementBaseline
from app.schemas.baseline import BaselineResponse
from app.services.project_access import get_project_or_404
from app.services.qa_chain import format_chunks_into_text
from app.services.retrieval import hybrid_search

logger = logging.getLogger(__name__)


class ExtractedRequirementItem(BaseModel):
    stable_id: str = Field(description="Stable id like REQ-001")
    title: str
    description: str
    category: str
    priority: str = "unknown"
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_citation_indexes: list[int] = Field(default_factory=list)


class ExtractedOpenQuestion(BaseModel):
    title: str
    description: str
    source_citation_indexes: list[int] = Field(default_factory=list)


class RequirementsExtractionResult(BaseModel):
    requirements: list[ExtractedRequirementItem] = Field(default_factory=list)
    open_questions: list[ExtractedOpenQuestion] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


EXTRACTION_QUERIES = [
    "functional requirements features user stories MVP scope",
    "technical constraints integrations APIs data requirements",
    "assumptions risks non-functional requirements deadlines",
]


async def _gather_project_chunks(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> list:
    seen: set[str] = set()
    chunks: list = []
    for query in EXTRACTION_QUERIES:
        rows = await hybrid_search(
            question=query,
            db=db,
            user_id=user_id,
            project_id=project_id,
            k=6,
        )
        for row in rows:
            chunk_id = str(row.id)
            if chunk_id not in seen:
                seen.add(chunk_id)
                chunks.append(row)
    return chunks[:20]


def _chunk_source_ref(chunk, user_id: UUID) -> dict[str, Any]:
    return {
        "document_id": str(chunk.doc_id),
        "chunk_id": str(chunk.id),
        "page": (chunk.page_num or 0) + 1,
        "excerpt": (chunk.content or "")[:300],
    }


async def extract_requirements_for_project(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> tuple[list[Requirement], list[str], list[str]]:
    await get_project_or_404(project_id, user_id, db)

    doc_count = await db.execute(
        select(func.count())
        .select_from(Document)
        .where(
            Document.project_id == project_id,
            Document.user_id == user_id,
            Document.status == Document_Status.READY,
        )
    )
    if int(doc_count.scalar_one()) == 0:
        raise HTTPException(
            status_code=400,
            detail="Upload and process at least one document before extracting requirements.",
        )

    chunks = await _gather_project_chunks(db, user_id, project_id)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No indexed content found for this project.",
        )

    context = format_chunks_into_text(chunks)

    prompt = PromptTemplate.from_template(
        """You are a senior product analyst helping a freelance developer or indie builder
structure a project from client documents.

Extract structured requirements from the context below. Be specific and grounded.
Use stable IDs like REQ-001, REQ-002 for requirements and Q-001 for open questions.
Categories must be one of: feature, constraint, integration, non_functional, assumption, risk.
Priority must be one of: must, should, could, unknown.
Reference source passages using citation indexes like [1], [2] from the context.

Also list ambiguities and contradictions found in the documents.

Context:
{context}
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(RequirementsExtractionResult)

    try:
        result: RequirementsExtractionResult = (prompt | model).invoke({"context": context})
    except Exception as e:
        logger.error(f"Requirements extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to extract requirements") from e

    # Remove existing working set before inserting fresh extraction
    from sqlalchemy import delete

    await db.execute(
        delete(Requirement).where(
            Requirement.project_id == project_id,
            Requirement.baseline_id.is_(None),
        )
    )

    created: list[Requirement] = []
    sort_order = 0

    for item in result.requirements:
        source_refs = []
        for idx in item.source_citation_indexes:
            if 1 <= idx <= len(chunks):
                source_refs.append(_chunk_source_ref(chunks[idx - 1], user_id))

        from app.services.requirements import _map_category, _map_priority

        req = Requirement(
            project_id=project_id,
            stable_id=item.stable_id,
            title=item.title,
            description=item.description,
            category=_map_category(item.category),
            priority=_map_priority(item.priority),
            status=RequirementStatus.PROPOSED,
            acceptance_criteria=item.acceptance_criteria or [],
            assumptions=item.assumptions or [],
            source_refs=source_refs,
            sort_order=sort_order,
        )
        sort_order += 1
        db.add(req)
        created.append(req)

    for q in result.open_questions:
        source_refs = []
        for idx in q.source_citation_indexes:
            if 1 <= idx <= len(chunks):
                source_refs.append(_chunk_source_ref(chunks[idx - 1], user_id))

        req = Requirement(
            project_id=project_id,
            stable_id=f"Q-{sort_order + 1:03d}",
            title=q.title,
            description=q.description,
            category=RequirementCategory.OPEN_QUESTION,
            status=RequirementStatus.PROPOSED,
            source_refs=source_refs,
            sort_order=sort_order,
        )
        sort_order += 1
        db.add(req)
        created.append(req)

    await db.commit()
    for req in created:
        await db.refresh(req)

    return created, result.ambiguities, result.contradictions


async def approve_baseline(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    label: str | None = None,
) -> BaselineResponse:
    await get_project_or_404(project_id, user_id, db)

    result = await db.execute(
        select(Requirement).where(
            Requirement.project_id == project_id,
            Requirement.baseline_id.is_(None),
            Requirement.status == RequirementStatus.CONFIRMED,
            Requirement.category != RequirementCategory.OPEN_QUESTION,
        )
    )
    confirmed = result.scalars().all()
    if not confirmed:
        raise HTTPException(
            status_code=400,
            detail="Confirm at least one requirement before approving a baseline.",
        )

    version_result = await db.execute(
        select(func.max(RequirementBaseline.version)).where(
            RequirementBaseline.project_id == project_id
        )
    )
    next_version = int(version_result.scalar_one() or 0) + 1

    snapshot = [
        {
            "stable_id": r.stable_id,
            "title": r.title,
            "description": r.description,
            "category": r.category.value,
            "priority": r.priority.value,
            "status": r.status.value,
            "acceptance_criteria": r.acceptance_criteria or [],
            "assumptions": r.assumptions or [],
            "source_refs": r.source_refs or [],
        }
        for r in confirmed
    ]

    await db.execute(
        update(RequirementBaseline)
        .where(
            RequirementBaseline.project_id == project_id,
            RequirementBaseline.status == BaselineStatus.APPROVED,
        )
        .values(status=BaselineStatus.SUPERSEDED)
    )

    baseline = RequirementBaseline(
        project_id=project_id,
        version=next_version,
        status=BaselineStatus.APPROVED,
        label=label or f"Baseline v{next_version}",
        snapshot=snapshot,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(baseline)
    await db.commit()
    await db.refresh(baseline)

    return BaselineResponse(
        id=baseline.id,
        project_id=baseline.project_id,
        version=baseline.version,
        status=baseline.status,
        label=baseline.label,
        snapshot=baseline.snapshot,
        approved_at=baseline.approved_at,
        created_at=baseline.created_at,
    )


async def get_current_baseline(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> BaselineResponse | None:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(RequirementBaseline)
        .where(
            RequirementBaseline.project_id == project_id,
            RequirementBaseline.status == BaselineStatus.APPROVED,
        )
        .order_by(RequirementBaseline.version.desc())
        .limit(1)
    )
    baseline = result.scalar_one_or_none()
    if baseline is None:
        return None
    return BaselineResponse(
        id=baseline.id,
        project_id=baseline.project_id,
        version=baseline.version,
        status=baseline.status,
        label=baseline.label,
        snapshot=baseline.snapshot,
        approved_at=baseline.approved_at,
        created_at=baseline.created_at,
    )
