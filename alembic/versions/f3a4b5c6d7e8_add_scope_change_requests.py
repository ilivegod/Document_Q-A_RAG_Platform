"""add scope_change_requests table

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE scopechangestatus AS ENUM ("
        "'pending_review', 'approved_change_order', 'rejected', 'converted_to_task'"
        ")"
    )

    op.create_table(
        "scope_change_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("client_description", sa.Text(), nullable=False),
        sa.Column("ai_is_out_of_scope", sa.Boolean(), nullable=False),
        sa.Column("ai_reasoning", sa.Text(), nullable=False),
        sa.Column("estimated_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending_review",
                "approved_change_order",
                "rejected",
                "converted_to_task",
                name="scopechangestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column("linked_task_id", sa.UUID(), nullable=True),
        sa.Column("linked_requirement_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["linked_requirement_id"], ["requirements.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scope_change_requests_project_id",
        "scope_change_requests",
        ["project_id"],
    )
    op.create_index(
        "ix_scope_change_requests_status",
        "scope_change_requests",
        ["status"],
    )
    op.create_index(
        "ix_scope_change_requests_linked_task_id",
        "scope_change_requests",
        ["linked_task_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scope_change_requests_linked_task_id", table_name="scope_change_requests"
    )
    op.drop_index(
        "ix_scope_change_requests_status", table_name="scope_change_requests"
    )
    op.drop_index(
        "ix_scope_change_requests_project_id", table_name="scope_change_requests"
    )
    op.drop_table("scope_change_requests")
    op.execute("DROP TYPE IF EXISTS scopechangestatus")
