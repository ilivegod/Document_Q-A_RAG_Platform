"""Prospecting domain: searches, leads, outreach."""

from enum import Enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ProspectSearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WebsiteStatus(str, Enum):
    NONE = "none"
    POOR = "poor"
    OK = "ok"
    UNKNOWN = "unknown"


class ProspectStatus(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    DISMISSED = "dismissed"
    CONTACTED = "contacted"
    CONVERTED = "converted"


class OutreachEmailStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"


class OutreachDomainStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class UserOutreachSettings(Base):
    __tablename__ = "user_outreach_settings"

    user_id = mapped_column(
        UUID,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    from_name = mapped_column(String(255), nullable=True)
    from_email = mapped_column(String(254), nullable=True)
    resend_domain_id = mapped_column(String(255), nullable=True)
    domain_name = mapped_column(String(255), nullable=True)
    domain_status: Mapped[OutreachDomainStatus] = mapped_column(
        SQLEnum(
            OutreachDomainStatus,
            name="outreachdomainstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=OutreachDomainStatus.NOT_CONFIGURED,
        nullable=False,
    )
    dns_records = mapped_column(JSONB, nullable=True)
    signature_block = mapped_column(Text, nullable=True)
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProspectSearch(Base):
    __tablename__ = "prospect_searches"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_query = mapped_column(String(500), nullable=False)
    industry_keywords = mapped_column(String(500), nullable=False)
    radius_km = mapped_column(Integer, nullable=False, default=10)
    filter_no_website = mapped_column(Boolean, nullable=False, default=False)
    filter_poor_website = mapped_column(Boolean, nullable=False, default=False)
    niche_notes = mapped_column(Text, nullable=True)
    status: Mapped[ProspectSearchStatus] = mapped_column(
        SQLEnum(
            ProspectSearchStatus,
            name="prospectsearchstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ProspectSearchStatus.PENDING,
        nullable=False,
        index=True,
    )
    result_count = mapped_column(Integer, nullable=False, default=0)
    error_message = mapped_column(Text, nullable=True)
    cancel_requested = mapped_column(Boolean, nullable=False, default=False)
    current_step = mapped_column(String(500), nullable=True)
    progress_log = mapped_column(JSONB, nullable=False, default=list)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)


class Prospect(Base):
    __tablename__ = "prospects"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_id = mapped_column(
        UUID,
        ForeignKey("prospect_searches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id = mapped_column(
        UUID,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    place_id = mapped_column(String(255), nullable=False, index=True)
    business_name = mapped_column(String(500), nullable=False)
    address = mapped_column(String(1000), nullable=True)
    phone = mapped_column(String(50), nullable=True)
    website_url = mapped_column(String(2000), nullable=True)
    website_status: Mapped[WebsiteStatus] = mapped_column(
        SQLEnum(
            WebsiteStatus,
            name="websitestatus",
            values_callable=_ENUM_VALUES,
        ),
        default=WebsiteStatus.UNKNOWN,
        nullable=False,
    )
    audit_signals = mapped_column(JSONB, nullable=True)
    fit_score = mapped_column(Integer, nullable=True)
    fit_summary = mapped_column(Text, nullable=True)
    pitch_angle = mapped_column(Text, nullable=True)
    contact_email = mapped_column(String(254), nullable=True)
    status: Mapped[ProspectStatus] = mapped_column(
        SQLEnum(
            ProspectStatus,
            name="prospectstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ProspectStatus.NEW,
        nullable=False,
        index=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prospect_id = mapped_column(
        UUID,
        ForeignKey("prospects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject = mapped_column(String(500), nullable=False)
    body_html = mapped_column(Text, nullable=False)
    body_text = mapped_column(Text, nullable=False)
    status: Mapped[OutreachEmailStatus] = mapped_column(
        SQLEnum(
            OutreachEmailStatus,
            name="outreachemailstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=OutreachEmailStatus.DRAFT,
        nullable=False,
        index=True,
    )
    resend_message_id = mapped_column(String(255), nullable=True)
    error_message = mapped_column(Text, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at = mapped_column(DateTime(timezone=True), nullable=True)
