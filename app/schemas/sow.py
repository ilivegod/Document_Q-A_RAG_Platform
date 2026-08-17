from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SowTierResponse(BaseModel):
    tier_key: str
    tier_name: str
    description: str = ""
    total_hours: float
    total_cost: float
    requirement_ids: list[str] = Field(default_factory=list)
    estimated_weeks: int = 4
    contingency_applied: bool = False


class SowDocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    hourly_rate: Decimal
    deposit_percentage: Decimal
    tiers: list[SowTierResponse]
    out_of_scope_items: list[str]
    labor_breakdown: list[dict] | None = None
    summary: str | None = None
    status: str
    generation_status: str
    accepted_tier_key: str | None = None
    accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SowDocumentUpdate(BaseModel):
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    deposit_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    out_of_scope_items: list[str] | None = None
    tiers: list[dict] | None = None
    passcode: str | None = Field(
        default=None,
        min_length=4,
        max_length=64,
        description="Optional portal passcode (stored hashed). Empty string clears passcode.",
    )


class PortalLinkResponse(BaseModel):
    token: str
    portal_url: str
    passcode_required: bool


class PublicPortalMetaResponse(BaseModel):
    project_name: str
    client_name: str | None = None
    passcode_required: bool
    sow_status: str | None = None
    can_submit_requests: bool = True


class PublicSowResponse(BaseModel):
    summary: str | None = None
    tiers: list[SowTierResponse]
    out_of_scope_items: list[str]
    status: str
    accepted_tier_key: str | None = None
    deposit_percentage: Decimal
    hourly_rate: Decimal


class SowAcceptRequest(BaseModel):
    tier_key: str = Field(min_length=1, max_length=64)
    passcode: str | None = None


class SowAcceptResponse(BaseModel):
    accepted_tier_key: str
    status: str
    message: str
