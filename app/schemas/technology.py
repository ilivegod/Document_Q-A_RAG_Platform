from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.technology_exploration import TechnologyExplorationStatus
from app.schemas.requirement import SourceRef


class TechnologyAlternative(BaseModel):
    name: str
    summary: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    best_for: str | None = None


class TechnologyResource(BaseModel):
    title: str
    url: str
    resource_type: Literal[
        "official_doc", "sdk", "tutorial", "github", "comparison", "other"
    ] = "other"


class TechnologyAnalysisBody(BaseModel):
    recommended: str
    confidence: Literal["high", "medium", "low"]
    summary: str
    alternatives: list[TechnologyAlternative] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    resources: list[TechnologyResource] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    requirements_addressed: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


class TechnologyExploreCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=2000)


class TechnologyExplorationResponse(BaseModel):
    id: UUID
    project_id: UUID
    topic: str
    status: TechnologyExplorationStatus
    analysis: TechnologyAnalysisBody
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
