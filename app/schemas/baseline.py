from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.requirement_baseline import BaselineStatus


class BaselineResponse(BaseModel):
    id: UUID
    project_id: UUID
    version: int
    status: BaselineStatus
    label: str | None = None
    snapshot: list[dict[str, Any]]
    approved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApproveBaselineRequest(BaseModel):
    label: str | None = Field(default=None, max_length=255)
