"""add technology_explorations table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE technologyexplorationstatus AS ENUM ('completed')"
    )

    op.create_table(
        "technology_explorations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "completed",
                name="technologyexplorationstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_technology_explorations_project_id",
        "technology_explorations",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_technology_explorations_project_id",
        table_name="technology_explorations",
    )
    op.drop_table("technology_explorations")
    op.execute("DROP TYPE IF EXISTS technologyexplorationstatus")
