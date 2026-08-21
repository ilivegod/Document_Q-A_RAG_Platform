"""add sales proposals and project prospect link

Revision ID: j7k8l9m0n1p2
Revises: i6j7k8l9m0n1
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "j7k8l9m0n1p2"
down_revision: Union[str, None] = "i6j7k8l9m0n1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE salesproposalstatus AS ENUM ("
        "'researching', 'awaiting_confirmation', 'drafting', 'draft', "
        "'approved', 'failed'"
        ")"
    )
    op.add_column(
        "projects",
        sa.Column("prospect_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_prospect_id",
        "projects",
        "prospects",
        ["prospect_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_projects_prospect_id", "projects", ["prospect_id"])

    op.create_table(
        "sales_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prospect_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "researching",
                "awaiting_confirmation",
                "drafting",
                "draft",
                "approved",
                "failed",
                name="salesproposalstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("proposal_kind", sa.String(length=64), nullable=True),
        sa.Column("proposal_kind_label", sa.String(length=255), nullable=True),
        sa.Column("user_intent", sa.Text(), nullable=True),
        sa.Column("research_summary", postgresql.JSONB(), nullable=True),
        sa.Column("confirmation_question", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision_notes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("current_step", sa.String(length=500), nullable=True),
        sa.Column(
            "progress_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_sales_proposals_user_id", "sales_proposals", ["user_id"])
    op.create_index("ix_sales_proposals_project_id", "sales_proposals", ["project_id"])
    op.create_index("ix_sales_proposals_status", "sales_proposals", ["status"])


def downgrade() -> None:
    op.drop_table("sales_proposals")
    op.drop_index("ix_projects_prospect_id", table_name="projects")
    op.drop_constraint("fk_projects_prospect_id", "projects", type_="foreignkey")
    op.drop_column("projects", "prospect_id")
    op.execute("DROP TYPE IF EXISTS salesproposalstatus")
