from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.change_request import ChangeRequestStatus, ImpactVerdict
from app.schemas.requirement import SourceRef


class ChangeImpactAnalysisBody(BaseModel):
    verdict: ImpactVerdict
    confidence: Literal["high", "medium", "low"]
    summary: str
    affected_requirement_ids: list[str] = Field(default_factory=list)
    mvp_impact: str | None = None
    risks: list[str] = Field(default_factory=list)
    client_questions: list[str] = Field(default_factory=list)
    suggested_response: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)


class ChangeRequestCreate(BaseModel):
    request_text: str = Field(min_length=1, max_length=5000)


class ChangeRequestResponse(BaseModel):
    id: UUID
    project_id: UUID
    baseline_id: UUID | None = None
    request_text: str
    status: ChangeRequestStatus
    analysis: ChangeImpactAnalysisBody | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
