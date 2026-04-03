from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.retrieval import similarity_search
from app.services.qa_chain import llm_prompt

from app.models.user import User
from app.dependencies.getUser import get_current_user

router = APIRouter()


@router.post("/documents/query")
async def query_document(
    question: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not question:
        return None
    retrieved_text = await similarity_search(question, db, current_user.id)
    result = llm_prompt(question, retrieved_text)

    return {
        "answer": result,
        "question": question,
        "sources": (
            [
                {"content": chunk.content, "page": (chunk.page_num or 0) + 1}
                for chunk in retrieved_text
            ]
            if "don't have enough information" not in result
            else []
        ),
    }
