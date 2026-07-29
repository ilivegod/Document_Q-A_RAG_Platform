"""AI work-breakdown proposals: generate a plan, apply only on approval."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity_event import ActivityActor
from app.models.milestone import Milestone, MilestoneStatus
from app.models.plan_proposal import PlanProposal, ProposalStatus, ProposalType
from app.models.requirement import Requirement, RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.services.execution import (
    get_proposal_or_404,
    list_milestones,
    list_proposals,
    list_tasks,
    record_activity,
)
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements

logger = logging.getLogger(__name__)


class ProposedMilestone(BaseModel):
    temp_id: str = Field(description="Local id like m1 for linking tasks")
    title: str
    description: str = ""


class ProposedTask(BaseModel):
    temp_id: str = Field(description="Local id like t1")
    title: str
    description: str = ""
    priority: str = "should"
    status: str = "next"
    milestone_temp_id: str | None = None
    requirement_stable_ids: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class WorkBreakdownResult(BaseModel):
    title: str = "Work breakdown"
    summary: str = ""
    milestones: list[ProposedMilestone] = Field(default_factory=list)
    tasks: list[ProposedTask] = Field(default_factory=list)


def _map_priority(value: str) -> TaskPriority:
    try:
        return TaskPriority(value)
    except ValueError:
        return TaskPriority.SHOULD


def _map_status(value: str) -> TaskStatus:
    try:
        return TaskStatus(value)
    except ValueError:
        return TaskStatus.NEXT


def _format_requirements(requirements: list[Requirement]) -> str:
    lines: list[str] = []
    for req in requirements:
        lines.append(
            f"- {req.stable_id}: {req.title} "
            f"({req.category.value}, {req.priority.value}, {req.status.value}) — "
            f"{(req.description or '')[:240]}"
        )
        if req.acceptance_criteria:
            for criterion in req.acceptance_criteria[:4]:
                lines.append(f"    AC: {criterion}")
    return "\n".join(lines) if lines else "No requirements."


def _format_existing_plan(milestones: list[Milestone], tasks: list[Task]) -> str:
    if not milestones and not tasks:
        return "No milestones or tasks yet."
    lines: list[str] = []
    for milestone in milestones:
        lines.append(f"- Milestone: {milestone.title} [{milestone.status.value}]")
    for task in tasks:
        lines.append(
            f"- Task: {task.title} [{task.status.value}] "
            f"(priority={task.priority.value})"
        )
    return "\n".join(lines)


def build_work_breakdown_payload(result: WorkBreakdownResult) -> dict[str, Any]:
    return {
        "milestones": [item.model_dump() for item in result.milestones],
        "tasks": [item.model_dump() for item in result.tasks],
    }


async def generate_work_breakdown_proposal(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> PlanProposal:
    await get_project_or_404(project_id, user_id, db)

    requirements, _open_questions = await list_working_requirements(db, project_id)
    usable = [
        req
        for req in requirements
        if req.status in (RequirementStatus.CONFIRMED, RequirementStatus.PROPOSED)
    ]
    confirmed = [req for req in usable if req.status == RequirementStatus.CONFIRMED]
    if not confirmed and not usable:
        raise HTTPException(
            status_code=400,
            detail="Confirm at least one requirement before generating a work breakdown.",
        )

    source_reqs = confirmed if confirmed else usable
    milestones = await list_milestones(db, project_id)
    tasks = await list_tasks(db, project_id)

    prompt = PromptTemplate.from_template(
        """You are a senior freelance technical lead helping a solo developer plan delivery.

Turn the project requirements into a practical work breakdown:
- 2 to 5 milestones for delivery phases
- Concrete implementation tasks (usually 1 to 3 per milestone, max ~15 total)
- Prefer actionable engineering work over vague planning
- Link each task to requirement stable IDs when possible
- Use priority must/should/could/unknown
- Default task status to "next" (use "now" only for one obvious first task)
- Do not invent requirements that are not grounded in the list
- Avoid duplicating existing milestones/tasks listed below

Existing plan:
{existing_plan}

Requirements:
{requirements}

Return a concise title and summary for the proposal.
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(WorkBreakdownResult)

    try:
        result: WorkBreakdownResult = await (prompt | model).ainvoke(
            {
                "requirements": _format_requirements(source_reqs),
                "existing_plan": _format_existing_plan(milestones, tasks),
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate work breakdown")

    if not result.milestones and not result.tasks:
        raise HTTPException(
            status_code=400,
            detail="The model returned an empty work breakdown. Try again after refining requirements.",
        )

    # Supersede any pending work-breakdown proposals so only one awaits review.
    pending = await list_proposals(
        db, project_id, status=ProposalStatus.PENDING
    )
    for existing in pending:
        if existing.proposal_type == ProposalType.WORK_BREAKDOWN:
            existing.status = ProposalStatus.SUPERSEDED
            existing.decided_at = datetime.now(timezone.utc)

    proposal = PlanProposal(
        project_id=project_id,
        proposal_type=ProposalType.WORK_BREAKDOWN,
        status=ProposalStatus.PENDING,
        title=result.title.strip() or "Work breakdown",
        summary=result.summary.strip() or None,
        payload=build_work_breakdown_payload(result),
    )
    db.add(proposal)
    await db.flush()

    await record_activity(
        db,
        project_id,
        summary=f"AI proposed work breakdown “{proposal.title}”",
        event_type="proposal.created",
        actor=ActivityActor.AI,
        entity_type="proposal",
        entity_id=proposal.id,
        payload={
            "milestone_count": len(result.milestones),
            "task_count": len(result.tasks),
        },
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def apply_work_breakdown_proposal(
    db: AsyncSession,
    project_id: UUID,
    proposal: PlanProposal,
    *,
    requirement_by_stable_id: dict[str, Requirement] | None = None,
) -> dict[str, int]:
    """Create milestones/tasks from an approved work-breakdown payload."""
    if proposal.proposal_type != ProposalType.WORK_BREAKDOWN:
        raise HTTPException(
            status_code=400,
            detail="Only work_breakdown proposals can be applied as a plan",
        )

    payload = proposal.payload or {}
    proposed_milestones = payload.get("milestones") or []
    proposed_tasks = payload.get("tasks") or []

    if requirement_by_stable_id is None:
        requirements, _ = await list_working_requirements(db, project_id)
        requirement_by_stable_id = {req.stable_id: req for req in requirements}

    existing_milestones = await list_milestones(db, project_id)
    sort_base = max((m.sort_order for m in existing_milestones), default=-1) + 1
    existing_tasks = await list_tasks(db, project_id)
    task_sort_base = max((t.sort_order for t in existing_tasks), default=-1) + 1

    temp_to_milestone_id: dict[str, UUID] = {}
    created_milestones = 0
    created_tasks = 0

    for index, item in enumerate(proposed_milestones):
        temp_id = str(item.get("temp_id") or f"m{index + 1}")
        title = (item.get("title") or "").strip()
        if not title:
            continue
        milestone = Milestone(
            project_id=project_id,
            title=title[:500],
            description=(item.get("description") or None),
            status=MilestoneStatus.PLANNED,
            sort_order=sort_base + index,
        )
        db.add(milestone)
        await db.flush()
        temp_to_milestone_id[temp_id] = milestone.id
        created_milestones += 1

    for index, item in enumerate(proposed_tasks):
        title = (item.get("title") or "").strip()
        if not title:
            continue

        milestone_temp = item.get("milestone_temp_id")
        milestone_id = (
            temp_to_milestone_id.get(str(milestone_temp))
            if milestone_temp
            else None
        )

        requirement_id = None
        for stable_id in item.get("requirement_stable_ids") or []:
            match = requirement_by_stable_id.get(str(stable_id))
            if match is not None:
                requirement_id = match.id
                break

        task = Task(
            project_id=project_id,
            milestone_id=milestone_id,
            requirement_id=requirement_id,
            title=title[:500],
            description=(item.get("description") or None),
            status=_map_status(str(item.get("status") or "next")),
            priority=_map_priority(str(item.get("priority") or "should")),
            acceptance_criteria=item.get("acceptance_criteria") or [],
            depends_on=[],
            sort_order=task_sort_base + index,
        )
        db.add(task)
        created_tasks += 1

    await record_activity(
        db,
        project_id,
        summary=(
            f"Applied work breakdown “{proposal.title}” "
            f"({created_milestones} milestones, {created_tasks} tasks)"
        ),
        event_type="proposal.applied",
        actor=ActivityActor.USER,
        entity_type="proposal",
        entity_id=proposal.id,
        payload={
            "milestones_created": created_milestones,
            "tasks_created": created_tasks,
        },
    )

    return {
        "milestones_created": created_milestones,
        "tasks_created": created_tasks,
    }


async def decide_and_maybe_apply_proposal(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    proposal_id: UUID,
    status: ProposalStatus,
) -> PlanProposal:
    await get_project_or_404(project_id, user_id, db)
    proposal = await get_proposal_or_404(db, project_id, proposal_id)

    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Only pending proposals can be decided",
        )
    if status not in (
        ProposalStatus.APPROVED,
        ProposalStatus.REJECTED,
        ProposalStatus.SUPERSEDED,
    ):
        raise HTTPException(
            status_code=400,
            detail="Decision must be approved, rejected, or superseded",
        )

    proposal.status = status
    proposal.decided_at = datetime.now(timezone.utc)

    if (
        status == ProposalStatus.APPROVED
        and proposal.proposal_type == ProposalType.WORK_BREAKDOWN
    ):
        await apply_work_breakdown_proposal(db, project_id, proposal)

    await record_activity(
        db,
        project_id,
        summary=f"Marked proposal “{proposal.title}” as {status.value}",
        event_type="proposal.decided",
        actor=ActivityActor.USER,
        entity_type="proposal",
        entity_id=proposal.id,
        payload={"status": status.value},
    )
    await db.commit()
    await db.refresh(proposal)
    return proposal
