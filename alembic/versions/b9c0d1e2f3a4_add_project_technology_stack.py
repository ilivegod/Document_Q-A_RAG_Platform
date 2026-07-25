"""add project technology stack and drop explorations

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE technologycategory AS ENUM ("
        "'frontend', 'backend', 'database', 'ai', 'authentication', "
        "'hosting', 'storage', 'testing', 'payments', 'devops', 'other'"
        ")"
    )
    op.execute("CREATE TYPE technologysource AS ENUM ('ai', 'manual')")

    op.create_table(
        "project_technologies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("catalog_id", sa.String(length=64), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "frontend",
                "backend",
                "database",
                "ai",
                "authentication",
                "hosting",
                "storage",
                "testing",
                "payments",
                "devops",
                "other",
                name="technologycategory",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            postgresql.ENUM(
                "ai",
                "manual",
                name="technologysource",
                create_type=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "catalog_id", name="uq_project_technology_catalog"
        ),
    )
    op.create_index(
        "ix_project_technologies_project_id",
        "project_technologies",
        ["project_id"],
    )

    op.drop_index(
        "ix_technology_explorations_project_id", table_name="technology_explorations"
    )
    op.drop_table("technology_explorations")
    op.execute("DROP TYPE IF EXISTS technologyexplorationstatus")

    op.alter_column(
        "projects",
        "technology_suggested",
        new_column_name="technology_generated",
    )


def downgrade() -> None:
    raise NotImplementedError("Technology stack migration is not reversible")
