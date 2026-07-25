"""add project analysis status fields

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE projectanalysisstatus AS ENUM ('idle', 'running', 'complete')"
    )
    op.add_column(
        "projects",
        sa.Column(
            "analysis_status",
            sa.Enum(
                "idle",
                "running",
                "complete",
                name="projectanalysisstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="idle",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "requirements_extracted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "technology_suggested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "last_analyzed_at")
    op.drop_column("projects", "technology_suggested")
    op.drop_column("projects", "requirements_extracted")
    op.drop_column("projects", "analysis_status")
    op.execute("DROP TYPE projectanalysisstatus")
