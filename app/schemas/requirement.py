from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.requirement import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
)


class SourceRef(BaseModel):
    document_id: str | None = None
    chunk_id: str | None = None
    page: int | None = None
    excerpt: str | None = None


class RequirementResponse(BaseModel):
    id: UUID
    project_id: UUID
    baseline_id: UUID | None = None
    stable_id: str
    title: str
    description: str | None = None
    category: RequirementCategory
    priority: RequirementPriority
    status: RequirementStatus
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    category: RequirementCategory | None = None
    priority: RequirementPriority | None = None
    status: RequirementStatus | None = None
    acceptance_criteria: list[str] | None = None
    assumptions: list[str] | None = None


class ExtractRequirementsResponse(BaseModel):
    requirements: list[RequirementResponse]
    open_questions: list[str]
    ambiguities: list[str]
    contradictions: list[str]


class RequirementsListResponse(BaseModel):
    requirements: list[RequirementResponse]
    open_questions: list[RequirementResponse]
