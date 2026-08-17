from uuid import UUID

from pydantic import BaseModel, Field


class AgencyProjectSnapshotResponse(BaseModel):
    id: UUID
    name: str
    client_name: str | None = None
    pipeline_stage: str
    health_score: int
    health_level: str
    health_summary: str
    blocked_count: int
    task_total: int
    pending_scope_changes: int


class AgencyOverviewResponse(BaseModel):
    projects: list[AgencyProjectSnapshotResponse]
    projects_by_stage: dict[str, list[AgencyProjectSnapshotResponse]]
    capacity_alerts: list[str] = Field(default_factory=list)
    totals: dict[str, int]


class PublicMilestoneSummary(BaseModel):
    title: str
    status: str
    target_date: str | None = None


class PublicReleaseSummary(BaseModel):
    version: str
    title: str
    notes: str | None = None
    published_at: str | None = None


class PublicHealthSummary(BaseModel):
    score: int
    level: str
    label: str
    summary: str
    active_milestones: int
    completion_ratio: float


class PublicDashboardResponse(BaseModel):
    health: PublicHealthSummary
    milestones: list[PublicMilestoneSummary]
    recent_releases: list[PublicReleaseSummary]
