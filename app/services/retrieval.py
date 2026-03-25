from sqlalchemy.ext.asyncio import AsyncSession
from app.services.embedding import embedding_model
from sqlalchemy import text


async def similarity_search(question: str, db: AsyncSession):
    question_vector = embedding_model.encode(question).tolist()

    result = await db.execute(
        text("SELECT * FROM chunk  ORDER BY embedding <=> :embedding LIMIT :k"),
        {"embedding": str(question_vector), "k": 5},
    )
    rows = result.fetchall()

    return rows
