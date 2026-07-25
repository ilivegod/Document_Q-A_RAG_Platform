"""add projects table and project_id scoping

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE projecttype AS ENUM ('client', 'indie')")
    op.execute("CREATE TYPE projectstatus AS ENUM ('active', 'archived')")

    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column(
            "project_type",
            postgresql.ENUM("client", "indie", name="projecttype", create_type=False),
            nullable=False,
            server_default="indie",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "archived", name="projectstatus", create_type=False),
            nullable=False,
            server_default="active",
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
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    op.add_column(
        "documents",
        sa.Column("project_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_project_id",
        "documents",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    op.add_column(
        "conversations",
        sa.Column("project_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_project_id",
        "conversations",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])

    # Backfill one default project per user who has documents or conversations.
    op.execute(
        """
        INSERT INTO projects (id, user_id, name, project_type, status)
        SELECT gen_random_uuid(), u.id, 'Imported documents', 'indie', 'active'
        FROM "user" u
        WHERE EXISTS (
            SELECT 1 FROM documents d WHERE d.user_id = u.id
        )
        OR EXISTS (
            SELECT 1 FROM conversations c WHERE c.user_id = u.id
        )
        """
    )

    op.execute(
        """
        UPDATE documents d
        SET project_id = p.id
        FROM projects p
        WHERE d.user_id = p.user_id
          AND p.name = 'Imported documents'
          AND d.project_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE conversations c
        SET project_id = COALESCE(
            (SELECT d.project_id FROM documents d WHERE d.id = c.document_id),
            (
                SELECT p.id
                FROM projects p
                WHERE p.user_id = c.user_id
                  AND p.name = 'Imported documents'
                LIMIT 1
            )
        )
        WHERE c.project_id IS NULL
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_conversations_user_global")
    op.execute(
        "ALTER TABLE conversations DROP CONSTRAINT IF EXISTS uq_conversations_user_document"
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_conversations_project_document
        ON conversations (project_id, document_id)
        WHERE document_id IS NOT NULL AND project_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_conversations_project_memory
        ON conversations (project_id)
        WHERE document_id IS NULL AND project_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_conversations_project_memory")
    op.execute("DROP INDEX IF EXISTS uq_conversations_project_document")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_conversations_user_global
        ON conversations (user_id) WHERE document_id IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE conversations
        ADD CONSTRAINT uq_conversations_user_document
        UNIQUE (user_id, document_id)
        """
    )

    op.drop_constraint("fk_conversations_project_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_project_id", table_name="conversations")
    op.drop_column("conversations", "project_id")

    op.drop_constraint("fk_documents_project_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_column("documents", "project_id")

    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
    op.execute("DROP TYPE IF EXISTS projectstatus")
    op.execute("DROP TYPE IF EXISTS projecttype")
