from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SalesProposalResearchRequest(BaseModel):
    user_intent: str | None = Field(
        default=None,
        description="Natural language intent, e.g. research and draft a website proposal",
    )


class SalesProposalConfirmRequest(BaseModel):
    proposal_kind: str | None = None
    custom_approach: str | None = None


class SalesProposalReviseRequest(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)


class SalesProposalResponse(BaseModel):
    id: UUID
    project_id: UUID
    prospect_id: UUID | None
    status: str
    proposal_kind: str | None
    proposal_kind_label: str | None
    user_intent: str | None
    research_summary: dict | None
    confirmation_question: str | None
    content_markdown: str | None
    revision_count: int
    revision_notes: list[dict]
    document_id: UUID | None
    error_message: str | None
    current_step: str | None
    progress_log: list[dict]
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
