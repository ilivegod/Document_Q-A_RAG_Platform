import logging
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, Document_Status
from app.models.requirement import Requirement
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.qa_chain import format_chunks_into_text
from app.services.requirements_merge import (
    ExtractMergeSummary,
    RequirementsExtractionResult,
    merge_extraction_into_requirements,
)
from app.services.retrieval import hybrid_search

logger = logging.getLogger(__name__)

# Re-export for callers/tests that imported from this module previously.
__all__ = [
    "ExtractMergeSummary",
    "RequirementsExtractionResult",
    "extract_requirements_for_project",
    "merge_extraction_into_requirements",
]

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


async def extract_requirements_for_project(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> tuple[list[Requirement], list[str], list[str], ExtractMergeSummary]:
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

    existing_result = await db.execute(
        select(Requirement).where(Requirement.project_id == project_id)
    )
    existing = list(existing_result.scalars().all())

    added_rows, updated_rows, summary = merge_extraction_into_requirements(
        existing,
        result,
        project_id=project_id,
        chunks=chunks,
    )

    for req in added_rows:
        db.add(req)

    await db.commit()
    for req in [*added_rows, *updated_rows]:
        await db.refresh(req)

    return [*added_rows, *updated_rows], result.ambiguities, result.contradictions, summary
