from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChangeRequestStatus(str, Enum):
    OPEN = "open"
    ANALYZED = "analyzed"


class ImpactVerdict(str, Enum):
    COVERED_BY_BASELINE = "covered_by_baseline"
    LIKELY_CHANGE_REQUEST = "likely_change_request"
    CONFLICTS_WITH_BASELINE = "conflicts_with_baseline"
    NEW_CAPABILITY = "new_capability"
    UNCLEAR = "unclear_needs_clarification"


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    baseline_id = mapped_column(
        UUID,
        ForeignKey("requirement_baselines.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_text = mapped_column(Text, nullable=False)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        SQLEnum(ChangeRequestStatus, name="changerequeststatus"),
        default=ChangeRequestStatus.OPEN,
        nullable=False,
    )
    analysis = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
