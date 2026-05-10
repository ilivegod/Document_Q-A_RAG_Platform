"""add email_verified column to user

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-10 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add email_verified to user. New accounts default to FALSE; existing
    accounts are backfilled to TRUE — they registered before verification
    existed, so retroactively marking them unverified would be poor UX.
    """
    # Add nullable first so the backfill doesn't violate NOT NULL on a
    # table with existing rows where the default isn't applied to those rows.
    # (Postgres applies DEFAULT only to new inserts, not to existing rows,
    # unless we explicitly backfill.)
    op.add_column(
        'user',
        sa.Column(
            'email_verified',
            sa.Boolean(),
            nullable=True,
        ),
    )

    # Backfill existing rows to TRUE.
    op.execute("UPDATE \"user\" SET email_verified = TRUE WHERE email_verified IS NULL")

    # Now lock down: NOT NULL + DEFAULT FALSE for new rows.
    op.alter_column(
        'user',
        'email_verified',
        nullable=False,
        server_default=sa.text('false'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'email_verified')