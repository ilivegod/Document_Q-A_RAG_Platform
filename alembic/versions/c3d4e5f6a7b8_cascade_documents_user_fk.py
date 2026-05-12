"""cascade documents.user_id FK on user deletion

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Change documents.user_id FK from NO ACTION to ON DELETE CASCADE so
    deleting a user atomically removes their documents (and via the
    existing chunks.doc_id CASCADE, all their chunks). This is what the
    delete-account flow relies on.

    Postgres doesn't support 'ALTER CONSTRAINT ... CASCADE' for FK
    references directly; we drop and re-create.
    """
    op.drop_constraint('documents_user_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_user_id_fkey',
        'documents',
        'user',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema. Restore the non-cascading FK."""
    op.drop_constraint('documents_user_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_user_id_fkey',
        'documents',
        'user',
        ['user_id'],
        ['id'],
    )