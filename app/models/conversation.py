from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base
from enum import Enum
import uuid


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Conversation(Base):
    __tablename__ = "conversations"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = mapped_column(
        UUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Message(Base):
    __tablename__ = "messages"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id = mapped_column(
        UUID,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole, name="messagerole", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    content = mapped_column(Text, nullable=False)
    # Stored only on assistant messages. Full source objects (chunk content,
    # bboxes, page info) duplicated here so conversations are self-contained
    # even if the underlying document or chunks are later deleted.
    sources = mapped_column(JSONB, nullable=True)
    has_answer = mapped_column(Boolean, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )