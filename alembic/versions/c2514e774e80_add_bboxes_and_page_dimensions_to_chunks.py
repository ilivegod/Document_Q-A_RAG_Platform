"""add bboxes and page dimensions to chunks

Revision ID: c2514e774e80
Revises: d7a3387824f1
Create Date: 2026-05-09 19:41:28.461320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2514e774e80'
down_revision: Union[str, Sequence[str], None] = 'd7a3387824f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chunk', sa.Column('bboxes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('chunk', sa.Column('page_width', sa.Integer(), nullable=True))
    op.add_column('chunk', sa.Column('page_height', sa.Integer(), nullable=True))

    # Existing rows have a non-null page_num already, so this is safe.
    op.alter_column('chunk', 'page_num',
               existing_type=sa.INTEGER(),
               nullable=False)

    # Recreate the FK with ON DELETE CASCADE so deleting a document also
    # deletes its chunks. The previous FK didn't have CASCADE.
    op.drop_constraint('chunk_doc_id_fkey', 'chunk', type_='foreignkey')
    op.create_foreign_key('chunk_doc_id_fkey', 'chunk', 'documents',
                          ['doc_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('chunk_doc_id_fkey', 'chunk', type_='foreignkey')
    op.create_foreign_key('chunk_doc_id_fkey', 'chunk', 'documents',
                          ['doc_id'], ['id'])
    op.alter_column('chunk', 'page_num',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('chunk', 'page_height')
    op.drop_column('chunk', 'page_width')
    op.drop_column('chunk', 'bboxes')
