"""add max_candidates to prospect searches

Revision ID: i6j7k8l9m0n1
Revises: h5b6c7d8e9f0
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i6j7k8l9m0n1"
down_revision: Union[str, None] = "h5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prospect_searches",
        sa.Column("max_candidates", sa.Integer(), nullable=False, server_default="15"),
    )
    op.alter_column("prospect_searches", "max_candidates", server_default=None)


def downgrade() -> None:
    op.drop_column("prospect_searches", "max_candidates")
