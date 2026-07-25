"""add is_approved to user and admin_approval token type

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-05-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_approved",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Existing accounts keep access after deploy
    op.execute('UPDATE "user" SET is_approved = TRUE')

    op.execute(
        "ALTER TYPE tokentype ADD VALUE IF NOT EXISTS 'admin_approval'"
    )


def downgrade() -> None:
    op.drop_column("user", "is_approved")
    # PostgreSQL does not support removing enum values safely
