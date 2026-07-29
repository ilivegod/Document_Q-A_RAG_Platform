"""Execution domain: tasks linked to milestones and requirements."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class TaskStatus(str, Enum):
    NOW = "now"
    NEXT = "next"
    BLOCKED = "blocked"
    DONE = "done"


class TaskPriority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    UNKNOWN = "unknown"


class Task(Base):
    __tablename__ = "tasks"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id = mapped_column(
        UUID,
        ForeignKey("milestones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requirement_id = mapped_column(
        UUID,
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(
            TaskStatus,
            name="taskstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=TaskStatus.NEXT,
        nullable=False,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SQLEnum(
            TaskPriority,
            name="taskpriority",
            values_callable=_ENUM_VALUES,
        ),
        default=TaskPriority.UNKNOWN,
        nullable=False,
    )
    estimate_hours = mapped_column(Float, nullable=True)
    acceptance_criteria = mapped_column(JSONB, nullable=True)
    blocker_reason = mapped_column(Text, nullable=True)
    depends_on = mapped_column(JSONB, nullable=True)  # list of task UUID strings
    sort_order = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
