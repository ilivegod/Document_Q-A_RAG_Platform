"""add user_id index and hnsw vector index

Revision ID: d07e409ac2ad
Revises: 8255f07c2da5
Create Date: 2026-05-03 16:45:58.930397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd07e409ac2ad'
down_revision: Union[str, Sequence[str], None] = '8255f07c2da5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # B-tree index on documents.user_id for fast per-user filtering
    # (used by GET /documents and the similarity search JOIN)
    op.create_index(
        "ix_documents_user_id",
        "documents",
        ["user_id"],
    )

    # HNSW index on chunk.embedding using cosine distance.
    # Matches the <=> operator used in retrieval.py.
    # Parameters: m=16 (graph connectivity), ef_construction=64 (build quality).
    # These are pgvector defaults — good general-purpose values.
    op.execute(
        """
        CREATE INDEX ix_chunk_embedding_hnsw
        ON chunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_chunk_embedding_hnsw")
    op.drop_index("ix_documents_user_id", table_name="documents")
