from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.retrieval import similarity_search
from app.services.qa_chain import llm_prompt
from app.schemas.query import QueryRequest, QueryResponse, Source
from app.models.user import User
from app.dependencies.getUser import get_current_user
from app.dependencies.rate_limit import limiter, get_user_id_key, QUERY_LIMIT

router = APIRouter()


@router.post("/documents/query", response_model=QueryResponse)
@limiter.limit(QUERY_LIMIT, key_func=get_user_id_key)
async def query_document(
    request: Request,
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
            chunk_id=str(chunk.id),
            content=chunk.content,
            page=(chunk.page_num or 0) + 1,
            bboxes=chunk.bboxes,
            page_width=chunk.page_width,
            page_height=chunk.page_height,
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