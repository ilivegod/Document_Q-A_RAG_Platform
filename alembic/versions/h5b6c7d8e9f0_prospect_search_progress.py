"""prospect search progress log and cancel

Revision ID: h5b6c7d8e9f0
Revises: g4a5b6c7d8e9
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h5b6c7d8e9f0"
down_revision: Union[str, None] = "g4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE prospectsearchstatus ADD VALUE IF NOT EXISTS 'cancelled'"
    )
    op.add_column(
        "prospect_searches",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "prospect_searches",
        sa.Column("current_step", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "prospect_searches",
        sa.Column(
            "progress_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.alter_column("prospect_searches", "cancel_requested", server_default=None)


def downgrade() -> None:
    op.drop_column("prospect_searches", "progress_log")
    op.drop_column("prospect_searches", "current_step")
    op.drop_column("prospect_searches", "cancel_requested")
    # PostgreSQL cannot remove enum values easily; leave 'cancelled' in type.
