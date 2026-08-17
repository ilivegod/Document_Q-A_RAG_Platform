"""Scope change requests from client portal."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ScopeChangeStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED_CHANGE_ORDER = "approved_change_order"
    REJECTED = "rejected"
    CONVERTED_TO_TASK = "converted_to_task"


class ScopeChangeRequest(Base):
    __tablename__ = "scope_change_requests"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_description = mapped_column(Text, nullable=False)
    ai_is_out_of_scope: Mapped[bool] = mapped_column(nullable=False)
    ai_reasoning = mapped_column(Text, nullable=False)
    estimated_hours = mapped_column(Numeric(6, 2), nullable=True)
    estimated_cost = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[ScopeChangeStatus] = mapped_column(
        SQLEnum(
            ScopeChangeStatus,
            name="scopechangestatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ScopeChangeStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
    )
    linked_task_id = mapped_column(
        UUID,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    linked_requirement_id = mapped_column(
        UUID,
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at = mapped_column(DateTime(timezone=True), nullable=True)
