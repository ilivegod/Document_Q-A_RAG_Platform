"""add change_requests table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE changerequeststatus AS ENUM ('open', 'analyzed')"
    )
    op.execute(
        "CREATE TYPE impactverdict AS ENUM ("
        "'covered_by_baseline', 'likely_change_request', "
        "'conflicts_with_baseline', 'new_capability', "
        "'unclear_needs_clarification')"
    )

    op.create_table(
        "change_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("baseline_id", sa.UUID(), nullable=True),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open", "analyzed",
                name="changerequeststatus", create_type=False,
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column("analysis", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["requirement_baselines.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_change_requests_project_id", "change_requests", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_change_requests_project_id", table_name="change_requests")
    op.drop_table("change_requests")
    op.execute("DROP TYPE IF EXISTS impactverdict")
    op.execute("DROP TYPE IF EXISTS changerequeststatus")
