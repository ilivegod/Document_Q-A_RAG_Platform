"""Execution domain: milestones for project delivery phases."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class MilestoneStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Milestone(Base):
    __tablename__ = "milestones"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text, nullable=True)
    status: Mapped[MilestoneStatus] = mapped_column(
        SQLEnum(
            MilestoneStatus,
            name="milestonestatus",
            values_callable=_ENUM_VALUES,
        ),
        default=MilestoneStatus.PLANNED,
        nullable=False,
    )
    sort_order = mapped_column(Integer, default=0, nullable=False)
    target_date = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
