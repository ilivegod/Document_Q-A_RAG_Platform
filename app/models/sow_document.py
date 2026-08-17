"""Agency domain: client-facing Statement of Work documents."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class SowStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SowGenerationStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class SowDocument(Base):
    __tablename__ = "sow_documents"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token = mapped_column(String(64), nullable=False, unique=True, index=True)
    hourly_rate = mapped_column(
        Numeric(10, 2), nullable=False, server_default="100.00"
    )
    deposit_percentage = mapped_column(
        Numeric(5, 2), nullable=False, server_default="30.00"
    )
    tiers = mapped_column(JSONB, nullable=False, default=list)
    out_of_scope_items = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    labor_breakdown = mapped_column(JSONB, nullable=True)
    summary = mapped_column(Text, nullable=True)
    status: Mapped[SowStatus] = mapped_column(
        SQLEnum(
            SowStatus,
            name="sowstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=SowStatus.DRAFT,
        nullable=False,
        index=True,
    )
    generation_status: Mapped[SowGenerationStatus] = mapped_column(
        SQLEnum(
            SowGenerationStatus,
            name="sowgenerationstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=SowGenerationStatus.IDLE,
        nullable=False,
    )
    accepted_tier_key = mapped_column(String(64), nullable=True)
    accepted_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
