from sqlalchemy.ext.asyncio import AsyncSession
from app.services.embedding import embedding_model
from sqlalchemy import text


async def similarity_search(question: str, db: AsyncSession, user_id):
    question_vector = embedding_model.encode(question).tolist()

    result = await db.execute(
        text(
            "SELECT chunk.* FROM chunk JOIN documents ON chunk.doc_id = documents.id WHERE documents.user_id = :user_id ORDER BY chunk.embedding <=> :embedding LIMIT :k"
        ),
        {"embedding": str(question_vector), "k": 5, "user_id": str(user_id)},
    )
    rows = result.fetchall()

    return rows
