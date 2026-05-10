"""create auth_tokens table

Revision ID: a1b2c3d4e5f6
Revises: c2514e774e80
Create Date: 2026-05-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c2514e774e80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type via raw DDL.
    #
    # We deliberately do NOT let SQLAlchemy auto-create the enum during
    # create_table — there's a known interaction where create_table walks
    # column types and emits CREATE TYPE even when create_type=False is set
    # on the column, leading to duplicate-type errors. Raw DDL + IF NOT EXISTS
    # sidesteps that entirely. The column below uses postgresql.ENUM with
    # create_type=False to make sure SQLAlchemy treats the type as
    # already-existing.
    op.execute(
        "CREATE TYPE tokentype AS ENUM ('PASSWORD_RESET', 'EMAIL_VERIFICATION')"
    )

    op.create_table(
        'auth_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column(
            'token_type',
            postgresql.ENUM(
                'PASSWORD_RESET',
                'EMAIL_VERIFICATION',
                name='tokentype',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['user.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_auth_tokens_token_hash'),
    )

    op.create_index(
        'ix_auth_tokens_user_type_used',
        'auth_tokens',
        ['user_id', 'token_type', 'used_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_auth_tokens_user_type_used', table_name='auth_tokens')
    op.drop_table('auth_tokens')
    op.execute("DROP TYPE IF EXISTS tokentype")