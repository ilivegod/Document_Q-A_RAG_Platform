"""add agency sow domain: pipeline_stage, sow_documents, client_portal_access

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE pipelinestage AS ENUM ("
        "'lead', 'proposal_sent', 'in_development', 'qa_review', 'handed_off'"
        ")"
    )
    op.execute(
        "CREATE TYPE sowstatus AS ENUM ('draft', 'sent', 'accepted', 'rejected')"
    )
    op.execute(
        "CREATE TYPE sowgenerationstatus AS ENUM ("
        "'idle', 'running', 'complete', 'failed'"
        ")"
    )

    op.add_column(
        "projects",
        sa.Column(
            "pipeline_stage",
            postgresql.ENUM(
                "lead",
                "proposal_sent",
                "in_development",
                "qa_review",
                "handed_off",
                name="pipelinestage",
                create_type=False,
            ),
            nullable=False,
            server_default="lead",
        ),
    )
    op.create_index("ix_projects_pipeline_stage", "projects", ["pipeline_stage"])

    op.create_table(
        "sow_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column(
            "hourly_rate",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="100.00",
        ),
        sa.Column(
            "deposit_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="30.00",
        ),
        sa.Column(
            "tiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "out_of_scope_items",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("labor_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "sent",
                "accepted",
                "rejected",
                name="sowstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "generation_status",
            postgresql.ENUM(
                "idle",
                "running",
                "complete",
                "failed",
                name="sowgenerationstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="idle",
        ),
        sa.Column("accepted_tier_key", sa.String(length=64), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_sow_documents_project_id", "sow_documents", ["project_id"])
    op.create_index("ix_sow_documents_status", "sow_documents", ["status"])
    op.create_index("ix_sow_documents_token", "sow_documents", ["token"])

    op.create_table(
        "client_portal_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("passcode_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "can_submit_requests",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        "ix_client_portal_access_project_id",
        "client_portal_access",
        ["project_id"],
    )
    op.create_index(
        "ix_client_portal_access_token",
        "client_portal_access",
        ["token"],
    )


def downgrade() -> None:
    op.drop_index("ix_client_portal_access_token", table_name="client_portal_access")
    op.drop_index(
        "ix_client_portal_access_project_id", table_name="client_portal_access"
    )
    op.drop_table("client_portal_access")

    op.drop_index("ix_sow_documents_token", table_name="sow_documents")
    op.drop_index("ix_sow_documents_status", table_name="sow_documents")
    op.drop_index("ix_sow_documents_project_id", table_name="sow_documents")
    op.drop_table("sow_documents")

    op.drop_index("ix_projects_pipeline_stage", table_name="projects")
    op.drop_column("projects", "pipeline_stage")

    op.execute("DROP TYPE IF EXISTS sowgenerationstatus")
    op.execute("DROP TYPE IF EXISTS sowstatus")
    op.execute("DROP TYPE IF EXISTS pipelinestage")
