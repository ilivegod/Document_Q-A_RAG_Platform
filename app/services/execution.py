"""CRUD helpers for the project execution domain."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityActor, ActivityEvent
from app.models.decision import Decision, DecisionStatus
from app.models.milestone import Milestone, MilestoneStatus
from app.models.plan_proposal import PlanProposal, ProposalStatus, ProposalType
from app.models.requirement import Requirement
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.execution import (
    ActivityEventResponse,
    DecisionResponse,
    MilestoneResponse,
    PlanProposalResponse,
    TaskResponse,
)


def _uuid_list(raw: Any) -> list[UUID]:
    if not raw:
        return []
    return [UUID(str(item)) for item in raw]


def milestone_to_response(row: Milestone) -> MilestoneResponse:
    return MilestoneResponse.model_validate(row)


def task_to_response(row: Task) -> TaskResponse:
    return TaskResponse(
        id=row.id,
        project_id=row.project_id,
        milestone_id=row.milestone_id,
        requirement_id=row.requirement_id,
        title=row.title,
        description=row.description,
        status=row.status,
        priority=row.priority,
        estimate_hours=row.estimate_hours,
        acceptance_criteria=row.acceptance_criteria or [],
        blocker_reason=row.blocker_reason,
        depends_on=_uuid_list(row.depends_on),
        sort_order=row.sort_order,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def decision_to_response(row: Decision) -> DecisionResponse:
    return DecisionResponse(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        rationale=row.rationale,
        status=row.status,
        related_requirement_ids=_uuid_list(row.related_requirement_ids),
        related_task_ids=_uuid_list(row.related_task_ids),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def activity_to_response(row: ActivityEvent) -> ActivityEventResponse:
    return ActivityEventResponse(
        id=row.id,
        project_id=row.project_id,
        actor=row.actor,
        event_type=row.event_type,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        summary=row.summary,
        payload=row.payload,
        created_at=row.created_at,
    )


def proposal_to_response(row: PlanProposal) -> PlanProposalResponse:
    return PlanProposalResponse(
        id=row.id,
        project_id=row.project_id,
        proposal_type=row.proposal_type,
        status=row.status,
        title=row.title,
        summary=row.summary,
        payload=row.payload or {},
        expires_at=row.expires_at,
        decided_at=row.decided_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def record_activity(
    db: AsyncSession,
    project_id: UUID,
    *,
    summary: str,
    event_type: str,
    actor: ActivityActor = ActivityActor.USER,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    payload: dict | None = None,
) -> ActivityEvent:
    event = ActivityEvent(
        project_id=project_id,
        actor=actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        payload=payload,
    )
    db.add(event)
    return event


async def get_milestone_or_404(
    db: AsyncSession, project_id: UUID, milestone_id: UUID
) -> Milestone:
    row = await db.get(Milestone, milestone_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return row


async def get_task_or_404(
    db: AsyncSession, project_id: UUID, task_id: UUID
) -> Task:
    row = await db.get(Task, task_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return row


async def get_decision_or_404(
    db: AsyncSession, project_id: UUID, decision_id: UUID
) -> Decision:
    row = await db.get(Decision, decision_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


async def get_proposal_or_404(
    db: AsyncSession, project_id: UUID, proposal_id: UUID
) -> PlanProposal:
    row = await db.get(PlanProposal, proposal_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return row


async def ensure_milestone_in_project(
    db: AsyncSession, project_id: UUID, milestone_id: UUID | None
) -> None:
    if milestone_id is None:
        return
    await get_milestone_or_404(db, project_id, milestone_id)


async def ensure_requirement_in_project(
    db: AsyncSession, project_id: UUID, requirement_id: UUID | None
) -> None:
    if requirement_id is None:
        return
    row = await db.get(Requirement, requirement_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Requirement not found")


async def list_milestones(db: AsyncSession, project_id: UUID) -> list[Milestone]:
    result = await db.execute(
        select(Milestone)
        .where(Milestone.project_id == project_id)
        .order_by(Milestone.sort_order.asc(), Milestone.created_at.asc())
    )
    return list(result.scalars().all())


async def list_tasks(
    db: AsyncSession,
    project_id: UUID,
    *,
    status: TaskStatus | None = None,
    milestone_id: UUID | None = None,
) -> list[Task]:
    stmt = select(Task).where(Task.project_id == project_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if milestone_id is not None:
        stmt = stmt.where(Task.milestone_id == milestone_id)
    stmt = stmt.order_by(Task.sort_order.asc(), Task.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_decisions(db: AsyncSession, project_id: UUID) -> list[Decision]:
    result = await db.execute(
        select(Decision)
        .where(Decision.project_id == project_id)
        .order_by(Decision.created_at.desc())
    )
    return list(result.scalars().all())


async def list_activity(
    db: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
) -> list[ActivityEvent]:
    result = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.project_id == project_id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_proposals(
    db: AsyncSession,
    project_id: UUID,
    *,
    status: ProposalStatus | None = None,
) -> list[PlanProposal]:
    stmt = select(PlanProposal).where(PlanProposal.project_id == project_id)
    if status is not None:
        stmt = stmt.where(PlanProposal.status == status)
    stmt = stmt.order_by(PlanProposal.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


def task_counts(tasks: list[Task]) -> dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    for task in tasks:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
    counts["total"] = len(tasks)
    return counts


# Re-export enums used by routers for convenience
__all__ = [
    "ActivityActor",
    "DecisionStatus",
    "MilestoneStatus",
    "ProposalStatus",
    "ProposalType",
    "TaskPriority",
    "TaskStatus",
    "activity_to_response",
    "decision_to_response",
    "ensure_milestone_in_project",
    "ensure_requirement_in_project",
    "get_decision_or_404",
    "get_milestone_or_404",
    "get_proposal_or_404",
    "get_task_or_404",
    "list_activity",
    "list_decisions",
    "list_milestones",
    "list_proposals",
    "list_tasks",
    "milestone_to_response",
    "proposal_to_response",
    "record_activity",
    "task_counts",
    "task_to_response",
    "timezone",
    "datetime",
]
