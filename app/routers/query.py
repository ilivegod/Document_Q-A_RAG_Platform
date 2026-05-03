from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.retrieval import similarity_search
from app.services.qa_chain import llm_prompt
from app.schemas.query import QueryRequest, QueryResponse, Source
from app.models.user import User
from app.dependencies.getUser import get_current_user

router = APIRouter()


@router.post("/documents/query", response_model=QueryResponse)
async def query_document(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    retrieved_chunks = await similarity_search(
        question=body.question,
        db=db,
        user_id=current_user.id,
        document_id=body.document_id,
        k=body.k,
    )

    # No chunks found — short-circuit, don't waste an LLM call.
    # This happens when: user has no docs, or document_id filter
    # matches a doc that hasn't finished processing yet.
    if not retrieved_chunks:
        return QueryResponse(
            question=body.question,
            answer=(
                "No content found to search. "
                "Make sure your documents have finished processing, "
                "then try again."
            ),
            has_answer=False,
            sources=[],
        )

    llm_answer = llm_prompt(body.question, retrieved_chunks)

    sources = (
        [
            Source(
                content=chunk.content,
                page=(chunk.page_num or 0) + 1,
            )
            for chunk in retrieved_chunks
        ]
        if llm_answer.has_answer
        else []
    )

    return QueryResponse(
        question=body.question,
        answer=llm_answer.answer,
        has_answer=llm_answer.has_answer,
        sources=sources,
    )