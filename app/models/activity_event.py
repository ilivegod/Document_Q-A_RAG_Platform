"""Execution domain: append-only activity timeline."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ActivityActor(str, Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor: Mapped[ActivityActor] = mapped_column(
        SQLEnum(
            ActivityActor,
            name="activityactor",
            values_callable=_ENUM_VALUES,
        ),
        default=ActivityActor.USER,
        nullable=False,
    )
    event_type = mapped_column(String(64), nullable=False, index=True)
    entity_type = mapped_column(String(64), nullable=True)
    entity_id = mapped_column(UUID, nullable=True)
    summary = mapped_column(Text, nullable=False)
    payload = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
