from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus, ProjectType, ProjectAnalysisStatus, PipelineStage, PipelineStage


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    client_name: str | None = None
    project_type: ProjectType = ProjectType.CLIENT


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    client_name: str | None = None
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    pipeline_stage: PipelineStage | None = None


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    client_name: str | None = None
    project_type: ProjectType
    status: ProjectStatus
    pipeline_stage: PipelineStage
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectAnalysisStatusResponse(BaseModel):
    analysis_status: ProjectAnalysisStatus
    requirements_extracted: bool
    technology_generated: bool
    analyzing: bool
    last_analyzed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
