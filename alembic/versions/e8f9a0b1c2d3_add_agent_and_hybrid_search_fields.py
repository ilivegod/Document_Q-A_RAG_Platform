"""add agent trace, nullable conversation document_id, chunk tsvector

Revision ID: e8f9a0b1c2d3
Revises: d7a3387824f1
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("agent_trace", JSONB, nullable=True))

    op.alter_column(
        "conversations",
        "document_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_conversations_user_global "
        "ON conversations (user_id) WHERE document_id IS NULL"
    )

    op.execute(
        "ALTER TABLE chunk ADD COLUMN IF NOT EXISTS content_tsv tsvector"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunk_content_tsv "
        "ON chunk USING gin (content_tsv)"
    )
    op.execute(
        "UPDATE chunk SET content_tsv = to_tsvector('english', content) "
        "WHERE content_tsv IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunk_content_tsv")
    op.drop_column("chunk", "content_tsv")
    op.execute("DROP INDEX IF EXISTS uq_conversations_user_global")
    op.alter_column(
        "conversations",
        "document_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("messages", "agent_trace")
