"""Sales proposal drafts: research, confirm, revise, approve → document."""

from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class SalesProposalStatus(str, Enum):
    RESEARCHING = "researching"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    DRAFTING = "drafting"
    DRAFT = "draft"
    APPROVED = "approved"
    FAILED = "failed"


class SalesProposal(Base):
    __tablename__ = "sales_proposals"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id = mapped_column(
        UUID, ForeignKey("prospects.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[SalesProposalStatus] = mapped_column(
        SQLEnum(
            SalesProposalStatus,
            name="salesproposalstatus",
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
        index=True,
    )
    proposal_kind = mapped_column(String(64), nullable=True)
    proposal_kind_label = mapped_column(String(255), nullable=True)
    user_intent = mapped_column(Text, nullable=True)
    research_summary = mapped_column(JSONB, nullable=True)
    confirmation_question = mapped_column(Text, nullable=True)
    content_markdown = mapped_column(Text, nullable=True)
    revision_count = mapped_column(Integer, nullable=False, default=0)
    revision_notes = mapped_column(JSONB, nullable=False, default=list)
    document_id = mapped_column(
        UUID, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    error_message = mapped_column(Text, nullable=True)
    current_step = mapped_column(String(500), nullable=True)
    progress_log = mapped_column(JSONB, nullable=False, default=list)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
