"""Pydantic schemas for QA runs, releases, and handoffs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QaCheckItemUpdate(BaseModel):
    status: str | None = None
    evidence_note: str | None = None
    title: str | None = None
    description: str | None = None


class QaCheckItemResponse(BaseModel):
    id: UUID
    qa_run_id: UUID
    requirement_id: UUID | None
    task_id: UUID | None
    title: str
    description: str | None
    status: str
    evidence_note: str | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QaRunCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = None
    seed_from_requirements: bool = True


class QaRunUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    status: str | None = None


class QaRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    status: str
    notes: str | None
    item_counts: dict[str, int] = Field(default_factory=dict)
    items: list[QaCheckItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ReleaseCreate(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    qa_run_id: UUID | None = None
    notes: str | None = None


class ReleaseUpdate(BaseModel):
    version: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = None
    qa_run_id: UUID | None = None
    status: str | None = None


class ReleaseResponse(BaseModel):
    id: UUID
    project_id: UUID
    qa_run_id: UUID | None
    version: str
    title: str
    status: str
    notes: str | None
    changelog: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class HandoffCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    release_id: UUID | None = None
    summary: str | None = None


class HandoffUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    summary: str | None = None
    release_id: UUID | None = None
    status: str | None = None


class HandoffResponse(BaseModel):
    id: UUID
    project_id: UUID
    release_id: UUID | None
    title: str
    status: str
    summary: str | None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DeliveryBoardResponse(BaseModel):
    qa_runs: list[QaRunResponse]
    releases: list[ReleaseResponse]
    handoffs: list[HandoffResponse]
    coverage: dict[str, Any]
