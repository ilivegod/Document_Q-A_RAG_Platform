"""Execution domain: approval-gated AI / plan proposals."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class ProposalType(str, Enum):
    WORK_BREAKDOWN = "work_breakdown"
    REPLAN = "replan"
    TASK_SPLIT = "task_split"
    RISK_ALERT = "risk_alert"
    NOTE = "note"


class PlanProposal(Base):
    __tablename__ = "plan_proposals"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposal_type: Mapped[ProposalType] = mapped_column(
        SQLEnum(
            ProposalType,
            name="proposaltype",
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
    )
    status: Mapped[ProposalStatus] = mapped_column(
        SQLEnum(
            ProposalStatus,
            name="proposalstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ProposalStatus.PENDING,
        nullable=False,
        index=True,
    )
    title = mapped_column(String(500), nullable=False)
    summary = mapped_column(Text, nullable=True)
    payload = mapped_column(JSONB, nullable=False, default=dict)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
