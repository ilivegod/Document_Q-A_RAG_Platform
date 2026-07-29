"""Delivery domain: project handoff summaries."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class HandoffStatus(str, Enum):
    DRAFT = "draft"
    FINAL = "final"


class Handoff(Base):
    __tablename__ = "handoffs"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id = mapped_column(
        UUID,
        ForeignKey("releases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = mapped_column(String(500), nullable=False)
    status: Mapped[HandoffStatus] = mapped_column(
        SQLEnum(
            HandoffStatus,
            name="handoffstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=HandoffStatus.DRAFT,
        nullable=False,
        index=True,
    )
    summary = mapped_column(Text, nullable=True)
    payload = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    finalized_at = mapped_column(DateTime(timezone=True), nullable=True)
