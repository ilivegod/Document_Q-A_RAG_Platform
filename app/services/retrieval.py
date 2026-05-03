import asyncio
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.services.embedding import embedding_model


async def similarity_search(
    question: str,
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None = None,
    k: int = 5,
):
    # Run the CPU-bound embedding call in a threadpool so it doesn't
    # block the event loop. encode() is synchronous and ~50-200ms.
    question_vector = await asyncio.to_thread(embedding_model.encode, question)
    question_vector_list = question_vector.tolist()

    # Build the SQL dynamically based on whether document_id is provided.
    # We can't conditionally inject SQL without parameterizing, so we
    # use two query variants — both still parameterized, both safe.
    if document_id is not None:
        query = text(
            """
            SELECT chunk.*
            FROM chunk
            JOIN documents ON chunk.doc_id = documents.id
            WHERE documents.user_id = :user_id
              AND documents.id = :document_id
            ORDER BY chunk.embedding <=> :embedding
            LIMIT :k
            """
        )
        params = {
            "embedding": str(question_vector_list),
            "k": k,
            "user_id": str(user_id),
            "document_id": str(document_id),
        }
    else:
        query = text(
            """
            SELECT chunk.*
            FROM chunk
            JOIN documents ON chunk.doc_id = documents.id
            WHERE documents.user_id = :user_id
            ORDER BY chunk.embedding <=> :embedding
            LIMIT :k
            """
        )
        params = {
            "embedding": str(question_vector_list),
            "k": k,
            "user_id": str(user_id),
        }

    result = await db.execute(query, params)
    return result.fetchall()