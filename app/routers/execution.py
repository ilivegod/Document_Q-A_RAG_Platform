"""Project execution API: milestones, tasks, decisions, activity, proposals."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.activity_event import ActivityActor
from app.models.decision import Decision
from app.models.milestone import Milestone
from app.models.plan_proposal import PlanProposal, ProposalStatus
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.schemas.execution import (
    ActivityEventCreate,
    ActivityEventResponse,
    CheckInResponse,
    DecisionCreate,
    DecisionResponse,
    DecisionUpdate,
    DeliveryHealthResponse,
    ExecutionBoardResponse,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
    PlanProposalCreate,
    PlanProposalDecide,
    PlanProposalResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.execution import (
    activity_to_response,
    decision_to_response,
    ensure_milestone_in_project,
    ensure_requirement_in_project,
    get_decision_or_404,
    get_milestone_or_404,
    get_task_or_404,
    list_activity,
    list_decisions,
    list_milestones,
    list_proposals,
    list_tasks,
    milestone_to_response,
    proposal_to_response,
    record_activity,
    task_counts,
    task_to_response,
)
from app.services.project_access import get_project_or_404

router = APIRouter(prefix="/projects/{project_id}", tags=["execution"])


# --- Board snapshot ---


@router.get("/execution", response_model=ExecutionBoardResponse)
async def get_execution_board(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.delivery_health import get_delivery_health, health_to_dict

    await get_project_or_404(project_id, current_user.id, db)
    milestones = await list_milestones(db, project_id)
    tasks = await list_tasks(db, project_id)
    decisions = await list_decisions(db, project_id)
    activity = await list_activity(db, project_id, limit=30)
    pending = await list_proposals(db, project_id, status=ProposalStatus.PENDING)
    health = await get_delivery_health(db, current_user.id, project_id)

    return ExecutionBoardResponse(
        milestones=[milestone_to_response(m) for m in milestones],
        tasks=[task_to_response(t) for t in tasks],
        decisions=[decision_to_response(d) for d in decisions],
        recent_activity=[activity_to_response(a) for a in activity],
        pending_proposals=[proposal_to_response(p) for p in pending],
        task_counts=task_counts(tasks),
        delivery_health=DeliveryHealthResponse(**health_to_dict(health)),
    )


@router.get("/delivery-health", response_model=DeliveryHealthResponse)
async def get_project_delivery_health(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.delivery_health import get_delivery_health, health_to_dict

    health = await get_delivery_health(db, current_user.id, project_id)
    return DeliveryHealthResponse(**health_to_dict(health))


@router.post("/check-in", response_model=CheckInResponse)
async def project_check_in(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.delivery_health import health_to_dict
    from app.services.project_checkin import run_project_check_in

    health, result, proposal = await run_project_check_in(
        db, current_user.id, project_id
    )
    return CheckInResponse(
        health=DeliveryHealthResponse(**health_to_dict(health)),
        summary=result.summary,
        highlights=result.highlights,
        risks=result.risks,
        suggested_next=result.suggested_next,
        proposal=proposal_to_response(proposal) if proposal else None,
    )


# --- Milestones ---


@router.get("/milestones", response_model=list[MilestoneResponse])
async def get_milestones(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_milestones(db, project_id)
    return [milestone_to_response(r) for r in rows]


@router.post("/milestones", response_model=MilestoneResponse, status_code=201)
async def create_milestone(
    project_id: UUID,
    body: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = Milestone(project_id=project_id, **body.model_dump())
    db.add(row)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Created milestone “{row.title}”",
        event_type="milestone.created",
        entity_type="milestone",
        entity_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return milestone_to_response(row)


@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    project_id: UUID,
    milestone_id: UUID,
    body: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_milestone_or_404(db, project_id, milestone_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    await record_activity(
        db,
        project_id,
        summary=f"Updated milestone “{row.title}”",
        event_type="milestone.updated",
        entity_type="milestone",
        entity_id=row.id,
        payload=updates,
    )
    await db.commit()
    await db.refresh(row)
    return milestone_to_response(row)


@router.delete("/milestones/{milestone_id}", status_code=204)
async def delete_milestone(
    project_id: UUID,
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_milestone_or_404(db, project_id, milestone_id)
    title = row.title
    await db.delete(row)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted milestone “{title}”",
        event_type="milestone.deleted",
        entity_type="milestone",
        entity_id=milestone_id,
    )
    await db.commit()
    return None


# --- Tasks ---


@router.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(
    project_id: UUID,
    status: TaskStatus | None = Query(default=None),
    milestone_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_tasks(
        db, project_id, status=status, milestone_id=milestone_id
    )
    return [task_to_response(r) for r in rows]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    project_id: UUID,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    await ensure_milestone_in_project(db, project_id, body.milestone_id)
    await ensure_requirement_in_project(db, project_id, body.requirement_id)

    data = body.model_dump()
    depends_on = data.pop("depends_on") or []
    row = Task(
        project_id=project_id,
        depends_on=[str(item) for item in depends_on],
        **data,
    )
    if row.status == TaskStatus.BLOCKED and not row.blocker_reason:
        raise HTTPException(
            status_code=400,
            detail="blocker_reason is required when status is blocked",
        )

    db.add(row)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Created task “{row.title}”",
        event_type="task.created",
        entity_type="task",
        entity_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return task_to_response(row)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_task_or_404(db, project_id, task_id)
    updates = body.model_dump(exclude_unset=True)

    if "milestone_id" in updates:
        await ensure_milestone_in_project(db, project_id, updates["milestone_id"])
    if "requirement_id" in updates:
        await ensure_requirement_in_project(db, project_id, updates["requirement_id"])
    if "depends_on" in updates and updates["depends_on"] is not None:
        updates["depends_on"] = [str(item) for item in updates["depends_on"]]

    for field, value in updates.items():
        setattr(row, field, value)

    if row.status == TaskStatus.BLOCKED and not row.blocker_reason:
        raise HTTPException(
            status_code=400,
            detail="blocker_reason is required when status is blocked",
        )
    if "status" in updates and row.status != TaskStatus.BLOCKED:
        row.blocker_reason = None

    await record_activity(
        db,
        project_id,
        summary=f"Updated task “{row.title}”",
        event_type="task.updated",
        entity_type="task",
        entity_id=row.id,
        payload={k: (str(v) if isinstance(v, UUID) else v) for k, v in updates.items()},
    )
    await db.commit()
    await db.refresh(row)
    return task_to_response(row)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    project_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_task_or_404(db, project_id, task_id)
    title = row.title
    await db.delete(row)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted task “{title}”",
        event_type="task.deleted",
        entity_type="task",
        entity_id=task_id,
    )
    await db.commit()
    return None


# --- Decisions ---


@router.get("/decisions", response_model=list[DecisionResponse])
async def get_decisions(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_decisions(db, project_id)
    return [decision_to_response(r) for r in rows]


@router.post("/decisions", response_model=DecisionResponse, status_code=201)
async def create_decision(
    project_id: UUID,
    body: DecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    data = body.model_dump()
    row = Decision(
        project_id=project_id,
        related_requirement_ids=[str(i) for i in data.pop("related_requirement_ids")],
        related_task_ids=[str(i) for i in data.pop("related_task_ids")],
        **data,
    )
    db.add(row)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Recorded decision “{row.title}”",
        event_type="decision.created",
        entity_type="decision",
        entity_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return decision_to_response(row)


@router.patch("/decisions/{decision_id}", response_model=DecisionResponse)
async def update_decision(
    project_id: UUID,
    decision_id: UUID,
    body: DecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_decision_or_404(db, project_id, decision_id)
    updates = body.model_dump(exclude_unset=True)
    if "related_requirement_ids" in updates and updates["related_requirement_ids"] is not None:
        updates["related_requirement_ids"] = [
            str(i) for i in updates["related_requirement_ids"]
        ]
    if "related_task_ids" in updates and updates["related_task_ids"] is not None:
        updates["related_task_ids"] = [str(i) for i in updates["related_task_ids"]]
    for field, value in updates.items():
        setattr(row, field, value)
    await record_activity(
        db,
        project_id,
        summary=f"Updated decision “{row.title}”",
        event_type="decision.updated",
        entity_type="decision",
        entity_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return decision_to_response(row)


@router.delete("/decisions/{decision_id}", status_code=204)
async def delete_decision(
    project_id: UUID,
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = await get_decision_or_404(db, project_id, decision_id)
    title = row.title
    await db.delete(row)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted decision “{title}”",
        event_type="decision.deleted",
        entity_type="decision",
        entity_id=decision_id,
    )
    await db.commit()
    return None


# --- Activity ---


@router.get("/activity", response_model=list[ActivityEventResponse])
async def get_activity(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_activity(db, project_id, limit=limit)
    return [activity_to_response(r) for r in rows]


@router.post("/activity", response_model=ActivityEventResponse, status_code=201)
async def create_activity_note(
    project_id: UUID,
    body: ActivityEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    event = await record_activity(
        db,
        project_id,
        summary=body.summary,
        event_type=body.event_type,
        actor=ActivityActor.USER,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        payload=body.payload,
    )
    await db.commit()
    await db.refresh(event)
    return activity_to_response(event)


# --- Proposals ---


@router.post(
    "/proposals/work-breakdown",
    response_model=PlanProposalResponse,
    status_code=201,
)
async def generate_work_breakdown(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.work_breakdown import generate_work_breakdown_proposal

    proposal = await generate_work_breakdown_proposal(
        db, current_user.id, project_id
    )
    return proposal_to_response(proposal)


@router.get("/proposals", response_model=list[PlanProposalResponse])
async def get_proposals(
    project_id: UUID,
    status: ProposalStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_proposals(db, project_id, status=status)
    return [proposal_to_response(r) for r in rows]


@router.post("/proposals", response_model=PlanProposalResponse, status_code=201)
async def create_proposal(
    project_id: UUID,
    body: PlanProposalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    row = PlanProposal(project_id=project_id, **body.model_dump())
    db.add(row)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Created proposal “{row.title}”",
        event_type="proposal.created",
        actor=ActivityActor.USER,
        entity_type="proposal",
        entity_id=row.id,
    )
    await db.commit()
    await db.refresh(row)
    return proposal_to_response(row)


@router.patch("/proposals/{proposal_id}", response_model=PlanProposalResponse)
async def decide_proposal(
    project_id: UUID,
    proposal_id: UUID,
    body: PlanProposalDecide,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.work_breakdown import decide_and_maybe_apply_proposal

    proposal = await decide_and_maybe_apply_proposal(
        db,
        current_user.id,
        project_id,
        proposal_id,
        body.status,
    )
    return proposal_to_response(proposal)
