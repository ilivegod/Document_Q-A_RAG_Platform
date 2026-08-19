"""add prospecting and outreach tables

Revision ID: g4a5b6c7d8e9
Revises: f3a4b5c6d7e8
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g4a5b6c7d8e9"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE outreachdomainstatus AS ENUM ("
        "'not_configured', 'pending', 'verified', 'failed'"
        ")"
    )
    op.execute(
        "CREATE TYPE prospectsearchstatus AS ENUM ("
        "'pending', 'running', 'complete', 'failed'"
        ")"
    )
    op.execute(
        "CREATE TYPE websitestatus AS ENUM ('none', 'poor', 'ok', 'unknown')"
    )
    op.execute(
        "CREATE TYPE prospectstatus AS ENUM ("
        "'new', 'qualified', 'dismissed', 'contacted', 'converted'"
        ")"
    )
    op.execute(
        "CREATE TYPE outreachemailstatus AS ENUM ("
        "'draft', 'approved', 'sent', 'failed'"
        ")"
    )

    op.create_table(
        "user_outreach_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("from_email", sa.String(length=254), nullable=True),
        sa.Column("resend_domain_id", sa.String(length=255), nullable=True),
        sa.Column("domain_name", sa.String(length=255), nullable=True),
        sa.Column(
            "domain_status",
            postgresql.ENUM(
                "not_configured",
                "pending",
                "verified",
                "failed",
                name="outreachdomainstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="not_configured",
        ),
        sa.Column("dns_records", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("signature_block", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "prospect_searches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("location_query", sa.String(length=500), nullable=False),
        sa.Column("industry_keywords", sa.String(length=500), nullable=False),
        sa.Column("radius_km", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("filter_no_website", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("filter_poor_website", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("niche_notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "complete",
                "failed",
                name="prospectsearchstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prospect_searches_user_id", "prospect_searches", ["user_id"])
    op.create_index("ix_prospect_searches_status", "prospect_searches", ["status"])

    op.create_table(
        "prospects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("search_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("place_id", sa.String(length=255), nullable=False),
        sa.Column("business_name", sa.String(length=500), nullable=False),
        sa.Column("address", sa.String(length=1000), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website_url", sa.String(length=2000), nullable=True),
        sa.Column(
            "website_status",
            postgresql.ENUM(
                "none",
                "poor",
                "ok",
                "unknown",
                name="websitestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("audit_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fit_score", sa.Integer(), nullable=True),
        sa.Column("fit_summary", sa.Text(), nullable=True),
        sa.Column("pitch_angle", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "new",
                "qualified",
                "dismissed",
                "contacted",
                "converted",
                name="prospectstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="new",
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["search_id"], ["prospect_searches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prospects_user_id", "prospects", ["user_id"])
    op.create_index("ix_prospects_search_id", "prospects", ["search_id"])
    op.create_index("ix_prospects_place_id", "prospects", ["place_id"])
    op.create_index("ix_prospects_status", "prospects", ["status"])
    op.create_index(
        "ix_prospects_user_place_id",
        "prospects",
        ["user_id", "place_id"],
        unique=True,
    )

    op.create_table(
        "outreach_emails",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("prospect_id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "approved",
                "sent",
                "failed",
                name="outreachemailstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("resend_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospect_id"], ["prospects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outreach_emails_user_id", "outreach_emails", ["user_id"])
    op.create_index("ix_outreach_emails_prospect_id", "outreach_emails", ["prospect_id"])
    op.create_index("ix_outreach_emails_status", "outreach_emails", ["status"])


def downgrade() -> None:
    op.drop_table("outreach_emails")
    op.drop_table("prospects")
    op.drop_table("prospect_searches")
    op.drop_table("user_outreach_settings")
    op.execute("DROP TYPE IF EXISTS outreachemailstatus")
    op.execute("DROP TYPE IF EXISTS prospectstatus")
    op.execute("DROP TYPE IF EXISTS websitestatus")
    op.execute("DROP TYPE IF EXISTS prospectsearchstatus")
    op.execute("DROP TYPE IF EXISTS outreachdomainstatus")
