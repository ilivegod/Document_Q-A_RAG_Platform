from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum
from sqlalchemy import ForeignKey, DateTime, String, func, Enum as SQLEnum
from sqlalchemy.orm import mapped_column, Mapped
import uuid


class Document_Status(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id"), nullable=False, index=True
    )
    file_name = mapped_column(String(255), nullable=False)
    file_type = mapped_column(String(), nullable=False)
    file_path = mapped_column(String(), nullable=False)
    status: Mapped[Document_Status] = mapped_column(
        SQLEnum(Document_Status),
        default=Document_Status.UPLOADED,
        nullable=False,
    )
    created_at = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )