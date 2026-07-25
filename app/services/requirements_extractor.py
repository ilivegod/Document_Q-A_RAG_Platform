import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, Document_Status
from app.models.requirement import Requirement, RequirementCategory, RequirementStatus
from app.services.llm_errors import raise_llm_http_error
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
        result: RequirementsExtractionResult = await (prompt | model).ainvoke(
            {"context": context}
        )
    except Exception as e:
        raise_llm_http_error(e, action="extract requirements")

    await db.execute(
        delete(Requirement).where(Requirement.project_id == project_id)
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
