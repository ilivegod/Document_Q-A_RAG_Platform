"""Execution domain: lightweight decision log."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class DecisionStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


class Decision(Base):
    __tablename__ = "decisions"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = mapped_column(String(500), nullable=False)
    rationale = mapped_column(Text, nullable=True)
    status: Mapped[DecisionStatus] = mapped_column(
        SQLEnum(
            DecisionStatus,
            name="decisionstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=DecisionStatus.ACTIVE,
        nullable=False,
    )
    related_requirement_ids = mapped_column(JSONB, nullable=True)
    related_task_ids = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
