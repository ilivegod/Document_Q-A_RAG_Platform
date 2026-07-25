"""remove baseline change request and decision workflows

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_project_decisions_technology_exploration_id",
        table_name="project_decisions",
    )
    op.drop_index("ix_project_decisions_project_id", table_name="project_decisions")
    op.drop_table("project_decisions")
    op.execute("DROP TYPE IF EXISTS decisionstatus")
    op.execute("DROP TYPE IF EXISTS decisioncategory")

    op.drop_index("ix_change_requests_project_id", table_name="change_requests")
    op.drop_table("change_requests")
    op.execute("DROP TYPE IF EXISTS impactverdict")
    op.execute("DROP TYPE IF EXISTS changerequeststatus")

    op.drop_index("ix_requirements_baseline_id", table_name="requirements")
    op.drop_constraint(
        "requirements_baseline_id_fkey", "requirements", type_="foreignkey"
    )
    op.drop_column("requirements", "baseline_id")

    op.drop_index(
        "ix_requirement_baselines_project_id", table_name="requirement_baselines"
    )
    op.drop_table("requirement_baselines")
    op.execute("DROP TYPE IF EXISTS baselinestatus")


def downgrade() -> None:
    raise NotImplementedError("Legacy workflow tables were permanently removed")
