"""add requirements and requirement_baselines tables

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE baselinestatus AS ENUM ('draft', 'approved', 'superseded')"
    )
    op.execute(
        "CREATE TYPE requirementcategory AS ENUM "
        "('feature', 'constraint', 'integration', 'non_functional', "
        "'assumption', 'risk', 'open_question')"
    )
    op.execute(
        "CREATE TYPE requirementpriority AS ENUM ('must', 'should', 'could', 'unknown')"
    )
    op.execute(
        "CREATE TYPE requirementstatus AS ENUM ('proposed', 'confirmed', 'rejected')"
    )

    op.create_table(
        "requirement_baselines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "approved", "superseded",
                name="baselinestatus", create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version", name="uq_baseline_project_version"),
    )
    op.create_index(
        "ix_requirement_baselines_project_id",
        "requirement_baselines",
        ["project_id"],
    )

    op.create_table(
        "requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("baseline_id", sa.UUID(), nullable=True),
        sa.Column("stable_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            postgresql.ENUM(
                "feature", "constraint", "integration", "non_functional",
                "assumption", "risk", "open_question",
                name="requirementcategory", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "must", "should", "could", "unknown",
                name="requirementpriority", create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "proposed", "confirmed", "rejected",
                name="requirementstatus", create_type=False,
            ),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("acceptance_criteria", postgresql.JSONB(), nullable=True),
        sa.Column("assumptions", postgresql.JSONB(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["baseline_id"], ["requirement_baselines.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_index("ix_requirements_baseline_id", "requirements", ["baseline_id"])


def downgrade() -> None:
    op.drop_index("ix_requirements_baseline_id", table_name="requirements")
    op.drop_index("ix_requirements_project_id", table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("ix_requirement_baselines_project_id", table_name="requirement_baselines")
    op.drop_table("requirement_baselines")
    op.execute("DROP TYPE IF EXISTS requirementstatus")
    op.execute("DROP TYPE IF EXISTS requirementpriority")
    op.execute("DROP TYPE IF EXISTS requirementcategory")
    op.execute("DROP TYPE IF EXISTS baselinestatus")
