"""add delivery domain: qa runs, releases, handoffs

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE qarunstatus AS ENUM ('draft', 'in_progress', 'passed', 'failed')"
    )
    op.execute(
        "CREATE TYPE qaitemstatus AS ENUM ('pending', 'passed', 'failed', 'skipped')"
    )
    op.execute("CREATE TYPE releasestatus AS ENUM ('draft', 'published')")
    op.execute("CREATE TYPE handoffstatus AS ENUM ('draft', 'final')")

    op.create_table(
        "qa_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "in_progress",
                "passed",
                "failed",
                name="qarunstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_runs_project_id", "qa_runs", ["project_id"])
    op.create_index("ix_qa_runs_status", "qa_runs", ["status"])

    op.create_table(
        "qa_check_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("qa_run_id", sa.UUID(), nullable=False),
        sa.Column("requirement_id", sa.UUID(), nullable=True),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "passed",
                "failed",
                "skipped",
                name="qaitemstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("evidence_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qa_check_items_qa_run_id", "qa_check_items", ["qa_run_id"])
    op.create_index(
        "ix_qa_check_items_requirement_id", "qa_check_items", ["requirement_id"]
    )
    op.create_index("ix_qa_check_items_task_id", "qa_check_items", ["task_id"])
    op.create_index("ix_qa_check_items_status", "qa_check_items", ["status"])

    op.create_table(
        "releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("qa_run_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "published",
                name="releasestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changelog", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_releases_project_id", "releases", ["project_id"])
    op.create_index("ix_releases_qa_run_id", "releases", ["qa_run_id"])
    op.create_index("ix_releases_status", "releases", ["status"])

    op.create_table(
        "handoffs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "final",
                name="handoffstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_id"], ["releases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_handoffs_project_id", "handoffs", ["project_id"])
    op.create_index("ix_handoffs_release_id", "handoffs", ["release_id"])
    op.create_index("ix_handoffs_status", "handoffs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_handoffs_status", table_name="handoffs")
    op.drop_index("ix_handoffs_release_id", table_name="handoffs")
    op.drop_index("ix_handoffs_project_id", table_name="handoffs")
    op.drop_table("handoffs")

    op.drop_index("ix_releases_status", table_name="releases")
    op.drop_index("ix_releases_qa_run_id", table_name="releases")
    op.drop_index("ix_releases_project_id", table_name="releases")
    op.drop_table("releases")

    op.drop_index("ix_qa_check_items_status", table_name="qa_check_items")
    op.drop_index("ix_qa_check_items_task_id", table_name="qa_check_items")
    op.drop_index("ix_qa_check_items_requirement_id", table_name="qa_check_items")
    op.drop_index("ix_qa_check_items_qa_run_id", table_name="qa_check_items")
    op.drop_table("qa_check_items")

    op.drop_index("ix_qa_runs_status", table_name="qa_runs")
    op.drop_index("ix_qa_runs_project_id", table_name="qa_runs")
    op.drop_table("qa_runs")

    op.execute("DROP TYPE handoffstatus")
    op.execute("DROP TYPE releasestatus")
    op.execute("DROP TYPE qaitemstatus")
    op.execute("DROP TYPE qarunstatus")
