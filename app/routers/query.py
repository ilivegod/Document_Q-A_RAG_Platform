from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.retrieval import similarity_search
from app.services.qa_chain import llm_prompt

router = APIRouter()


@router.post("/documents/query")
async def query_document(question: str, db: AsyncSession = Depends(get_db)):
    if not question:
        return None
    retrieved_text = await similarity_search(question, db)
    result = llm_prompt(question, retrieved_text)

    return {"answer": result, "question": question}
