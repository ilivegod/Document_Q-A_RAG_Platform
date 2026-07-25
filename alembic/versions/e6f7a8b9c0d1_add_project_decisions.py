"""add project_decisions table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE decisioncategory AS ENUM "
        "('architecture', 'technology', 'scope', 'process', 'other')"
    )
    op.execute(
        "CREATE TYPE decisionstatus AS ENUM "
        "('proposed', 'accepted', 'superseded')"
    )

    op.create_table(
        "project_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("technology_exploration_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "architecture",
                "technology",
                "scope",
                "process",
                "other",
                name="decisioncategory",
                create_type=False,
            ),
            nullable=False,
            server_default="technology",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "proposed",
                "accepted",
                "superseded",
                name="decisionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("chosen_option", sa.Text(), nullable=False),
        sa.Column("alternatives_considered", postgresql.JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("consequences", postgresql.JSONB(), nullable=True),
        sa.Column("related_requirement_ids", postgresql.JSONB(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["technology_exploration_id"],
            ["technology_explorations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_decisions_project_id",
        "project_decisions",
        ["project_id"],
    )
    op.create_index(
        "ix_project_decisions_technology_exploration_id",
        "project_decisions",
        ["technology_exploration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_decisions_technology_exploration_id",
        table_name="project_decisions",
    )
    op.drop_index("ix_project_decisions_project_id", table_name="project_decisions")
    op.drop_table("project_decisions")
    op.execute("DROP TYPE IF EXISTS decisionstatus")
    op.execute("DROP TYPE IF EXISTS decisioncategory")
