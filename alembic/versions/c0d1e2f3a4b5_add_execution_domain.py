"""add execution domain: milestones tasks decisions activity proposals

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE milestonestatus AS ENUM ('planned', 'active', 'completed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE taskstatus AS ENUM ('now', 'next', 'blocked', 'done')"
    )
    op.execute(
        "CREATE TYPE taskpriority AS ENUM ('must', 'should', 'could', 'unknown')"
    )
    op.execute(
        "CREATE TYPE decisionstatus AS ENUM ('active', 'superseded', 'retracted')"
    )
    op.execute(
        "CREATE TYPE activityactor AS ENUM ('user', 'ai', 'system')"
    )
    op.execute(
        "CREATE TYPE proposaltype AS ENUM ("
        "'work_breakdown', 'replan', 'task_split', 'risk_alert', 'note'"
        ")"
    )
    op.execute(
        "CREATE TYPE proposalstatus AS ENUM ("
        "'pending', 'approved', 'rejected', 'superseded', 'expired'"
        ")"
    )

    op.create_table(
        "milestones",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "planned",
                "active",
                "completed",
                "cancelled",
                name="milestonestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_milestones_project_id", "milestones", ["project_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("milestone_id", sa.UUID(), nullable=True),
        sa.Column("requirement_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "now",
                "next",
                "blocked",
                "done",
                name="taskstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="next",
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "must",
                "should",
                "could",
                "unknown",
                name="taskpriority",
                create_type=False,
            ),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("estimate_hours", sa.Float(), nullable=True),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
        sa.Column("depends_on", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["requirement_id"], ["requirements.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])
    op.create_index("ix_tasks_milestone_id", "tasks", ["milestone_id"])
    op.create_index("ix_tasks_requirement_id", "tasks", ["requirement_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active",
                "superseded",
                "retracted",
                name="decisionstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "related_requirement_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "related_task_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_project_id", "decisions", ["project_id"])

    op.create_table(
        "activity_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column(
            "actor",
            postgresql.ENUM(
                "user",
                "ai",
                "system",
                name="activityactor",
                create_type=False,
            ),
            nullable=False,
            server_default="user",
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_events_project_id", "activity_events", ["project_id"])
    op.create_index("ix_activity_events_event_type", "activity_events", ["event_type"])
    op.create_index("ix_activity_events_created_at", "activity_events", ["created_at"])

    op.create_table(
        "plan_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column(
            "proposal_type",
            postgresql.ENUM(
                "work_breakdown",
                "replan",
                "task_split",
                "risk_alert",
                "note",
                name="proposaltype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "superseded",
                "expired",
                name="proposalstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_plan_proposals_project_id", "plan_proposals", ["project_id"])
    op.create_index("ix_plan_proposals_status", "plan_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_plan_proposals_status", table_name="plan_proposals")
    op.drop_index("ix_plan_proposals_project_id", table_name="plan_proposals")
    op.drop_table("plan_proposals")

    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_index("ix_activity_events_project_id", table_name="activity_events")
    op.drop_table("activity_events")

    op.drop_index("ix_decisions_project_id", table_name="decisions")
    op.drop_table("decisions")

    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_requirement_id", table_name="tasks")
    op.drop_index("ix_tasks_milestone_id", table_name="tasks")
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_milestones_project_id", table_name="milestones")
    op.drop_table("milestones")

    op.execute("DROP TYPE IF EXISTS proposalstatus")
    op.execute("DROP TYPE IF EXISTS proposaltype")
    op.execute("DROP TYPE IF EXISTS activityactor")
    op.execute("DROP TYPE IF EXISTS decisionstatus")
    op.execute("DROP TYPE IF EXISTS taskpriority")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS milestonestatus")
