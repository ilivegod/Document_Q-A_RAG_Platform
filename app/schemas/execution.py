from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.activity_event import ActivityActor
from app.models.decision import DecisionStatus
from app.models.milestone import MilestoneStatus
from app.models.plan_proposal import ProposalStatus, ProposalType
from app.models.task import TaskPriority, TaskStatus


# --- Milestones ---


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    status: MilestoneStatus = MilestoneStatus.PLANNED
    sort_order: int = 0
    target_date: datetime | None = None


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: MilestoneStatus | None = None
    sort_order: int | None = None
    target_date: datetime | None = None


class MilestoneResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: str | None = None
    status: MilestoneStatus
    sort_order: int
    target_date: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Tasks ---


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    milestone_id: UUID | None = None
    requirement_id: UUID | None = None
    status: TaskStatus = TaskStatus.NEXT
    priority: TaskPriority = TaskPriority.UNKNOWN
    estimate_hours: float | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    blocker_reason: str | None = None
    depends_on: list[UUID] = Field(default_factory=list)
    sort_order: int = 0


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    milestone_id: UUID | None = None
    requirement_id: UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    estimate_hours: float | None = None
    acceptance_criteria: list[str] | None = None
    blocker_reason: str | None = None
    depends_on: list[UUID] | None = None
    sort_order: int | None = None


class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    milestone_id: UUID | None = None
    requirement_id: UUID | None = None
    title: str
    description: str | None = None
    status: TaskStatus
    priority: TaskPriority
    estimate_hours: float | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    blocker_reason: str | None = None
    depends_on: list[UUID] = Field(default_factory=list)
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Decisions ---


class DecisionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    rationale: str | None = None
    status: DecisionStatus = DecisionStatus.ACTIVE
    related_requirement_ids: list[UUID] = Field(default_factory=list)
    related_task_ids: list[UUID] = Field(default_factory=list)


class DecisionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    rationale: str | None = None
    status: DecisionStatus | None = None
    related_requirement_ids: list[UUID] | None = None
    related_task_ids: list[UUID] | None = None


class DecisionResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    rationale: str | None = None
    status: DecisionStatus
    related_requirement_ids: list[UUID] = Field(default_factory=list)
    related_task_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Activity ---


class ActivityEventCreate(BaseModel):
    summary: str = Field(min_length=1)
    event_type: str = Field(default="note", min_length=1, max_length=64)
    entity_type: str | None = None
    entity_id: UUID | None = None
    payload: dict | None = None


class ActivityEventResponse(BaseModel):
    id: UUID
    project_id: UUID
    actor: ActivityActor
    event_type: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    summary: str
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Proposals ---


class PlanProposalCreate(BaseModel):
    proposal_type: ProposalType
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    payload: dict = Field(default_factory=dict)
    expires_at: datetime | None = None


class PlanProposalDecide(BaseModel):
    status: ProposalStatus


class PlanProposalResponse(BaseModel):
    id: UUID
    project_id: UUID
    proposal_type: ProposalType
    status: ProposalStatus
    title: str
    summary: str | None = None
    payload: dict = Field(default_factory=dict)
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeliveryHealthResponse(BaseModel):
    score: int
    level: str
    summary: str
    task_counts: dict[str, int]
    blocked_count: int
    done_ratio: float
    requirement_coverage: float
    uncovered_confirmed_requirements: int
    open_question_count: int
    active_milestone_count: int
    signals: list[str]


class CheckInResponse(BaseModel):
    health: DeliveryHealthResponse
    summary: str
    highlights: list[str]
    risks: list[str]
    suggested_next: list[str]
    proposal: PlanProposalResponse | None = None


class ExecutionBoardResponse(BaseModel):
    """Grouped execution snapshot for the upcoming UI."""

    milestones: list[MilestoneResponse]
    tasks: list[TaskResponse]
    decisions: list[DecisionResponse]
    recent_activity: list[ActivityEventResponse]
    pending_proposals: list[PlanProposalResponse]
    task_counts: dict[str, int]
    delivery_health: DeliveryHealthResponse | None = None
