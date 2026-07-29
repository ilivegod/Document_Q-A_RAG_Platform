"""Delivery domain: QA acceptance runs and checklist items."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class QaRunStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class QaItemStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QaRun(Base):
    __tablename__ = "qa_runs"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = mapped_column(String(500), nullable=False)
    status: Mapped[QaRunStatus] = mapped_column(
        SQLEnum(
            QaRunStatus,
            name="qarunstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=QaRunStatus.DRAFT,
        nullable=False,
        index=True,
    )
    notes = mapped_column(Text, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)


class QaCheckItem(Base):
    __tablename__ = "qa_check_items"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    qa_run_id = mapped_column(
        UUID, ForeignKey("qa_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id = mapped_column(
        UUID,
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id = mapped_column(
        UUID,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text, nullable=True)
    status: Mapped[QaItemStatus] = mapped_column(
        SQLEnum(
            QaItemStatus,
            name="qaitemstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=QaItemStatus.PENDING,
        nullable=False,
        index=True,
    )
    evidence_note = mapped_column(Text, nullable=True)
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
