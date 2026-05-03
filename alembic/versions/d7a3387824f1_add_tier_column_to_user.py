"""add tier column to user

Revision ID: d7a3387824f1
Revises: d07e409ac2ad
Create Date: 2026-05-03 21:42:27.927309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a3387824f1'
down_revision: Union[str, Sequence[str], None] = 'd07e409ac2ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type explicitly first.
    # op.add_column doesn't auto-create enum types (op.create_table does).
    user_tier_enum = sa.Enum('FREE', 'PRO', 'BUSINESS', name='usertier')
    user_tier_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'user',
        sa.Column(
            'tier',
            user_tier_enum,
            nullable=False,
            server_default='FREE',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'tier')
    sa.Enum(name='usertier').drop(op.get_bind(), checkfirst=True)