from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_decision import DecisionCategory, DecisionStatus


class DecisionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    category: DecisionCategory = DecisionCategory.TECHNOLOGY
    context: str | None = None
    chosen_option: str = Field(min_length=1)
    alternatives_considered: list[str] = Field(default_factory=list)
    rationale: str | None = None
    consequences: list[str] = Field(default_factory=list)
    related_requirement_ids: list[str] = Field(default_factory=list)
    technology_exploration_id: UUID | None = None


class DecisionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    category: DecisionCategory | None = None
    status: DecisionStatus | None = None
    context: str | None = None
    chosen_option: str | None = Field(default=None, min_length=1)
    alternatives_considered: list[str] | None = None
    rationale: str | None = None
    consequences: list[str] | None = None
    related_requirement_ids: list[str] | None = None


class DecisionResponse(BaseModel):
    id: UUID
    project_id: UUID
    technology_exploration_id: UUID | None = None
    title: str
    category: DecisionCategory
    status: DecisionStatus
    context: str | None = None
    chosen_option: str
    alternatives_considered: list[str] = Field(default_factory=list)
    rationale: str | None = None
    consequences: list[str] = Field(default_factory=list)
    related_requirement_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
