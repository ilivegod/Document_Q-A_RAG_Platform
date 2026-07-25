from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project_technology import TechnologyCategory, TechnologySource


class TechnologyCatalogItemResponse(BaseModel):
    id: str
    name: str
    category: TechnologyCategory
    docs_url: str
    icon_slug: str

    model_config = ConfigDict(from_attributes=True)


class ProjectTechnologyResponse(BaseModel):
    id: UUID
    project_id: UUID
    catalog_id: str
    name: str
    category: TechnologyCategory
    docs_url: str
    icon_slug: str
    source: TechnologySource
    rationale: str | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectTechnologyCreate(BaseModel):
    catalog_id: str = Field(min_length=1, max_length=64)
    rationale: str | None = None


class TechnologyStackResponse(BaseModel):
    categories: dict[str, list[ProjectTechnologyResponse]]

    model_config = ConfigDict(from_attributes=True)
