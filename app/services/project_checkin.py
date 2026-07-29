"""Project check-in: AI review with optional approval-gated replan proposal."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity_event import ActivityActor
from app.models.plan_proposal import PlanProposal, ProposalStatus, ProposalType
from app.models.task import Task, TaskStatus
from app.services.delivery_health import (
    DeliveryHealth,
    get_delivery_health,
    recent_activity_summary,
)
from app.services.execution import (
    list_milestones,
    list_proposals,
    list_tasks,
    record_activity,
)
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements
from app.services.work_breakdown import ProposedTask, _map_priority, _map_status

logger = logging.getLogger(__name__)


class ProposedTaskUpdate(BaseModel):
    task_id: str
    status: str | None = None
    priority: str | None = None
    blocker_reason: str | None = None
    title: str | None = None


class CheckInLLMResult(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_next: list[str] = Field(default_factory=list)
    recommend_replan: bool = False
    replan_title: str = "Suggested replan"
    replan_summary: str = ""
    task_updates: list[ProposedTaskUpdate] = Field(default_factory=list)
    new_tasks: list[ProposedTask] = Field(default_factory=list)


def build_replan_payload(result: CheckInLLMResult) -> dict[str, Any]:
    return {
        "task_updates": [item.model_dump() for item in result.task_updates],
        "new_tasks": [item.model_dump() for item in result.new_tasks],
        "notes": result.suggested_next,
    }


def _format_tasks(tasks: list[Task]) -> str:
    if not tasks:
        return "No tasks."
    lines = []
    for task in tasks:
        lines.append(
            f"- id={task.id} | {task.title} | status={task.status.value} | "
            f"priority={task.priority.value}"
            + (
                f" | blocked={task.blocker_reason}"
                if task.status == TaskStatus.BLOCKED and task.blocker_reason
                else ""
            )
        )
    return "\n".join(lines)


async def run_project_check_in(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> tuple[DeliveryHealth, CheckInLLMResult, PlanProposal | None]:
    await get_project_or_404(project_id, user_id, db)

    health = await get_delivery_health(db, user_id, project_id)
    tasks = await list_tasks(db, project_id)
    milestones = await list_milestones(db, project_id)
    requirements, open_questions = await list_working_requirements(db, project_id)
    activity = await recent_activity_summary(db, project_id)

    req_lines = []
    for req in requirements:
        req_lines.append(
            f"- {req.stable_id}: {req.title} [{req.status.value}] "
            f"({req.priority.value})"
        )
    for q in open_questions:
        req_lines.append(f"- OPEN {q.stable_id}: {q.title}")

    milestone_lines = [
        f"- {m.title} [{m.status.value}]" for m in milestones
    ] or ["None"]

    prompt = PromptTemplate.from_template(
        """You are an AI project manager for a solo developer.

Review the current project state and produce a concise check-in.
Be practical and specific. Prefer fewer, high-signal recommendations.

If delivery is healthy, set recommend_replan=false and leave task_updates/new_tasks empty.
If there is clear friction (blockers, no Now work, overloaded Now, uncovered requirements),
set recommend_replan=true and propose concrete task_updates and/or a few new_tasks.
Only reference real task ids from the task list when updating.

Delivery health:
score={score} level={level}
signals:
{signals}

Tasks:
{tasks}

Milestones:
{milestones}

Requirements:
{requirements}

Recent activity:
{activity}
"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(CheckInLLMResult)

    try:
        result: CheckInLLMResult = await (prompt | model).ainvoke(
            {
                "score": health.score,
                "level": health.level,
                "signals": "\n".join(f"- {s}" for s in health.signals),
                "tasks": _format_tasks(tasks),
                "milestones": "\n".join(milestone_lines),
                "requirements": "\n".join(req_lines) if req_lines else "None",
                "activity": activity,
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="run project check-in")

    # Only keep updates that reference existing tasks.
    valid_ids = {str(task.id) for task in tasks}
    result.task_updates = [
        update
        for update in result.task_updates
        if update.task_id in valid_ids
    ]

    proposal: PlanProposal | None = None
    should_replan = result.recommend_replan and (
        bool(result.task_updates) or bool(result.new_tasks)
    )

    if should_replan:
        pending = await list_proposals(db, project_id, status=ProposalStatus.PENDING)
        for existing in pending:
            if existing.proposal_type == ProposalType.REPLAN:
                existing.status = ProposalStatus.SUPERSEDED
                existing.decided_at = datetime.now(timezone.utc)

        proposal = PlanProposal(
            project_id=project_id,
            proposal_type=ProposalType.REPLAN,
            status=ProposalStatus.PENDING,
            title=(result.replan_title or "Suggested replan").strip()[:500],
            summary=(result.replan_summary or result.summary or None),
            payload=build_replan_payload(result),
        )
        db.add(proposal)
        await db.flush()

    await record_activity(
        db,
        project_id,
        summary="Completed project check-in",
        event_type="checkin.completed",
        actor=ActivityActor.AI,
        entity_type="proposal" if proposal else "project",
        entity_id=proposal.id if proposal else project_id,
        payload={
            "health_score": health.score,
            "health_level": health.level,
            "recommend_replan": should_replan,
        },
    )
    await db.commit()
    if proposal is not None:
        await db.refresh(proposal)

    return health, result, proposal


async def apply_replan_proposal(
    db: AsyncSession,
    project_id: UUID,
    proposal: PlanProposal,
) -> dict[str, int]:
    if proposal.proposal_type != ProposalType.REPLAN:
        raise HTTPException(
            status_code=400,
            detail="Only replan proposals can be applied this way",
        )

    payload = proposal.payload or {}
    updates = payload.get("task_updates") or []
    new_tasks = payload.get("new_tasks") or []

    tasks = await list_tasks(db, project_id)
    by_id = {str(task.id): task for task in tasks}
    updated = 0
    created = 0

    for item in updates:
        task = by_id.get(str(item.get("task_id")))
        if task is None:
            continue
        if item.get("title"):
            task.title = str(item["title"])[:500]
        if item.get("status"):
            task.status = _map_status(str(item["status"]))
        if item.get("priority"):
            task.priority = _map_priority(str(item["priority"]))
        if "blocker_reason" in item:
            reason = item.get("blocker_reason")
            task.blocker_reason = str(reason) if reason else None
        if task.status == TaskStatus.BLOCKED and not task.blocker_reason:
            task.blocker_reason = "Blocked by approved replan"
        if task.status != TaskStatus.BLOCKED:
            task.blocker_reason = None
        updated += 1

    sort_base = max((task.sort_order for task in tasks), default=-1) + 1
    for index, item in enumerate(new_tasks):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        task = Task(
            project_id=project_id,
            title=title[:500],
            description=item.get("description") or None,
            status=_map_status(str(item.get("status") or "next")),
            priority=_map_priority(str(item.get("priority") or "should")),
            acceptance_criteria=item.get("acceptance_criteria") or [],
            depends_on=[],
            sort_order=sort_base + index,
            blocker_reason=(
                item.get("blocker_reason")
                if str(item.get("status") or "") == "blocked"
                else None
            ),
        )
        db.add(task)
        created += 1

    await record_activity(
        db,
        project_id,
        summary=(
            f"Applied replan “{proposal.title}” "
            f"({updated} updates, {created} new tasks)"
        ),
        event_type="proposal.applied",
        actor=ActivityActor.USER,
        entity_type="proposal",
        entity_id=proposal.id,
        payload={"tasks_updated": updated, "tasks_created": created},
    )
    return {"tasks_updated": updated, "tasks_created": created}
