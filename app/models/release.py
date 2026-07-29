"""Delivery domain: release records and notes."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ReleaseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Release(Base):
    __tablename__ = "releases"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    qa_run_id = mapped_column(
        UUID,
        ForeignKey("qa_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version = mapped_column(String(64), nullable=False)
    title = mapped_column(String(500), nullable=False)
    status: Mapped[ReleaseStatus] = mapped_column(
        SQLEnum(
            ReleaseStatus,
            name="releasestatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ReleaseStatus.DRAFT,
        nullable=False,
        index=True,
    )
    notes = mapped_column(Text, nullable=True)
    changelog = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    published_at = mapped_column(DateTime(timezone=True), nullable=True)
