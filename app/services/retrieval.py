import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding import embedding_model


async def similarity_search(
    question: str,
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None = None,
    project_id: UUID | None = None,
    k: int = 5,
):
    question_vector = await asyncio.to_thread(embedding_model.encode, question)
    question_vector_list = question_vector.tolist()

    filters = ["documents.user_id = :user_id"]
    params: dict = {
        "embedding": str(question_vector_list),
        "k": k,
        "user_id": str(user_id),
    }
    if document_id is not None:
        filters.append("documents.id = :document_id")
        params["document_id"] = str(document_id)
    if project_id is not None:
        filters.append("documents.project_id = :project_id")
        params["project_id"] = str(project_id)

    where_clause = " AND ".join(filters)
    query = text(
        f"""
        SELECT chunk.*
        FROM chunk
        JOIN documents ON chunk.doc_id = documents.id
        WHERE {where_clause}
        ORDER BY chunk.embedding <=> :embedding
        LIMIT :k
        """
    )

    result = await db.execute(query, params)
    return result.fetchall()


async def keyword_search(
    question: str,
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None = None,
    project_id: UUID | None = None,
    k: int = 5,
):
    """Full-text search using PostgreSQL tsvector."""
    ts_query = "plainto_tsquery('english', :query)"
    filters = ["documents.user_id = :user_id", f"chunk.content_tsv @@ {ts_query}"]
    params: dict = {"query": question, "k": k, "user_id": str(user_id)}
    if document_id is not None:
        filters.append("documents.id = :document_id")
        params["document_id"] = str(document_id)
    if project_id is not None:
        filters.append("documents.project_id = :project_id")
        params["project_id"] = str(project_id)

    where_clause = " AND ".join(filters)
    query = text(
        f"""
        SELECT chunk.*
        FROM chunk
        JOIN documents ON chunk.doc_id = documents.id
        WHERE {where_clause}
        ORDER BY ts_rank(chunk.content_tsv, {ts_query}) DESC
        LIMIT :k
        """
    )

    result = await db.execute(query, params)
    rows = result.fetchall()
    if rows:
        return rows
  # Fallback to vector search if FTS returns nothing (e.g. missing tsvector)
    return await similarity_search(
        question, db, user_id, document_id, project_id, k
    )


async def hybrid_search(
    question: str,
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID | None = None,
    project_id: UUID | None = None,
    k: int = 5,
    alpha: float = 0.7,
):
    """Combine vector similarity and BM25-style ts_rank with configurable alpha."""
    question_vector = await asyncio.to_thread(embedding_model.encode, question)
    question_vector_list = question_vector.tolist()

    filters = ["documents.user_id = :user_id"]
    params: dict = {
        "embedding": str(question_vector_list),
        "query": question,
        "k": k * 3,
        "user_id": str(user_id),
        "alpha": alpha,
        "one_minus_alpha": 1.0 - alpha,
    }
    if document_id is not None:
        filters.append("documents.id = :document_id")
        params["document_id"] = str(document_id)
    if project_id is not None:
        filters.append("documents.project_id = :project_id")
        params["project_id"] = str(project_id)

    where_clause = " AND ".join(filters)
    query = text(
        f"""
        WITH ranked AS (
            SELECT
                chunk.*,
                (1 - (chunk.embedding <=> :embedding)) AS vec_score,
                COALESCE(
                    ts_rank(chunk.content_tsv, plainto_tsquery('english', :query)),
                    0
                ) AS text_score
            FROM chunk
            JOIN documents ON chunk.doc_id = documents.id
            WHERE {where_clause}
        ),
        scored AS (
            SELECT *,
                (:alpha * vec_score + :one_minus_alpha * text_score) AS combined_score
            FROM ranked
        )
        SELECT id, doc_id, chunk_index, content, embedding, page_num,
               start_char, end_char, bboxes, page_width, page_height
        FROM scored
        ORDER BY combined_score DESC
        LIMIT :k
        """
    )
    result = await db.execute(query, {**params, "k": k})
    rows = result.fetchall()
    if rows:
        return rows
    return await similarity_search(
        question, db, user_id, document_id, project_id, k
    )


async def get_page_content(
    db: AsyncSession,
    user_id: UUID,
    document_id: UUID,
    page_number: int,
) -> str:
    """Return concatenated chunk text for a 1-indexed page."""
    page_index = page_number - 1
    query = text(
        """
        SELECT chunk.content
        FROM chunk
        JOIN documents ON chunk.doc_id = documents.id
        WHERE documents.user_id = :user_id
          AND documents.id = :document_id
          AND chunk.page_num = :page_num
        ORDER BY chunk.chunk_index ASC
        """
    )
    result = await db.execute(
        query,
        {
            "user_id": str(user_id),
            "document_id": str(document_id),
            "page_num": page_index,
        },
    )
    rows = result.fetchall()
    if not rows:
        return ""
    return "\n".join(r.content for r in rows)


async def backfill_chunk_tsvector(db: AsyncSession, doc_id: UUID | None = None) -> None:
    """Populate content_tsv for chunks (called after ingest or migration)."""
    if doc_id is not None:
        await db.execute(
            text(
                """
                UPDATE chunk
                SET content_tsv = to_tsvector('english', content)
                WHERE doc_id = :doc_id
                """
            ),
            {"doc_id": str(doc_id)},
        )
    else:
        await db.execute(
            text(
                """
                UPDATE chunk
                SET content_tsv = to_tsvector('english', content)
                WHERE content_tsv IS NULL
                """
            )
        )
    await db.flush()
