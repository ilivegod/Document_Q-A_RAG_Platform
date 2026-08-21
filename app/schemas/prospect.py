from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.prospect import (
    OutreachDomainStatus,
    OutreachEmailStatus,
    ProspectSearchStatus,
    ProspectStatus,
    WebsiteStatus,
)


class PlaceAutocompleteSuggestion(BaseModel):
    description: str
    place_id: str


ALLOWED_MAX_CANDIDATES = frozenset({15, 20, 25, 30, 35, 40, 45, 50})


class ProspectSearchCreate(BaseModel):
    location_query: str = Field(min_length=2, max_length=500)
    industry_keywords: str = Field(min_length=2, max_length=500)
    radius_km: int = Field(default=10, ge=1, le=50)
    filter_no_website: bool = False
    filter_poor_website: bool = False
    max_candidates: int = Field(default=15)
    niche_notes: str | None = None

    @field_validator("max_candidates")
    @classmethod
    def validate_max_candidates(cls, value: int) -> int:
        if value not in ALLOWED_MAX_CANDIDATES:
            raise ValueError(
                "max_candidates must be one of 15, 20, 25, 30, 35, 40, 45, or 50"
            )
        return value


class ProspectSearchResponse(BaseModel):
    id: UUID
    location_query: str
    industry_keywords: str
    radius_km: int
    filter_no_website: bool
    filter_poor_website: bool
    max_candidates: int
    niche_notes: str | None
    status: ProspectSearchStatus
    result_count: int
    error_message: str | None
    cancel_requested: bool = False
    current_step: str | None = None
    progress_log: list[dict] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None


class ProspectResponse(BaseModel):
    id: UUID
    search_id: UUID | None
    project_id: UUID | None
    place_id: str
    business_name: str
    address: str | None
    phone: str | None
    website_url: str | None
    website_status: WebsiteStatus
    audit_signals: dict | None
    fit_score: int | None
    fit_summary: str | None
    pitch_angle: str | None
    contact_email: str | None
    status: ProspectStatus
    created_at: datetime
    updated_at: datetime


class ProspectUpdate(BaseModel):
    contact_email: str | None = None
    status: ProspectStatus | None = None


class ProspectConvertResponse(BaseModel):
    prospect: ProspectResponse
    project_id: UUID


class OutreachSettingsResponse(BaseModel):
    from_name: str | None
    from_email: str | None
    domain_name: str | None
    domain_status: OutreachDomainStatus
    dns_records: list | None
    signature_block: str | None
    daily_send_limit: int
    sends_today: int


class OutreachSettingsUpdate(BaseModel):
    from_name: str | None = None
    from_email: str | None = None
    signature_block: str | None = None


class OutreachDomainCreate(BaseModel):
    domain_name: str = Field(min_length=3, max_length=255)


class OutreachEmailResponse(BaseModel):
    id: UUID
    prospect_id: UUID
    subject: str
    body_html: str
    body_text: str
    status: OutreachEmailStatus
    resend_message_id: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None


class OutreachEmailUpdate(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    status: OutreachEmailStatus | None = None
