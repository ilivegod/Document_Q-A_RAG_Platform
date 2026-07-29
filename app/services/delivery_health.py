"""Delivery health signals derived from execution + requirements state."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.milestone import Milestone, MilestoneStatus
from app.models.requirement import Requirement, RequirementStatus
from app.models.task import Task, TaskStatus
from app.services.execution import list_activity, list_milestones, list_tasks
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements


@dataclass
class DeliveryHealth:
    score: int
    level: str  # healthy | at_risk | critical | not_started
    summary: str
    task_counts: dict[str, int]
    blocked_count: int
    done_ratio: float
    requirement_coverage: float
    uncovered_confirmed_requirements: int
    open_question_count: int
    active_milestone_count: int
    signals: list[str]


def _task_counts(tasks: list[Task]) -> dict[str, int]:
    counts = {status.value: 0 for status in TaskStatus}
    for task in tasks:
        counts[task.status.value] = counts.get(task.status.value, 0) + 1
    counts["total"] = len(tasks)
    return counts


def compute_delivery_health(
    *,
    tasks: list[Task],
    milestones: list[Milestone],
    requirements: list[Requirement],
    open_questions: list[Requirement],
) -> DeliveryHealth:
    counts = _task_counts(tasks)
    total_tasks = counts["total"]
    blocked = counts.get("blocked", 0)
    done = counts.get("done", 0)
    now = counts.get("now", 0)

    confirmed = [
        req
        for req in requirements
        if req.status == RequirementStatus.CONFIRMED
    ]
    covered_ids = {
        task.requirement_id
        for task in tasks
        if task.requirement_id is not None
    }
    uncovered = [
        req for req in confirmed if req.id not in covered_ids
    ]
    coverage = (
        (len(confirmed) - len(uncovered)) / len(confirmed)
        if confirmed
        else 0.0
    )
    done_ratio = done / total_tasks if total_tasks else 0.0

    signals: list[str] = []
    score = 70

    if total_tasks == 0:
        return DeliveryHealth(
            score=0,
            level="not_started",
            summary="No execution tasks yet. Generate or add a plan to start tracking delivery.",
            task_counts=counts,
            blocked_count=0,
            done_ratio=0.0,
            requirement_coverage=coverage,
            uncovered_confirmed_requirements=len(uncovered),
            open_question_count=len(open_questions),
            active_milestone_count=sum(
                1 for m in milestones if m.status == MilestoneStatus.ACTIVE
            ),
            signals=["No tasks on the board"],
        )

    if blocked > 0:
        score -= min(35, blocked * 12)
        signals.append(f"{blocked} blocked task{'s' if blocked != 1 else ''}")
    if now == 0 and counts.get("next", 0) > 0:
        score -= 8
        signals.append("Nothing in Now — pick the next task")
    if now > 3:
        score -= 10
        signals.append("Too many Now tasks — focus the active set")
    if coverage < 0.5 and confirmed:
        score -= 15
        signals.append(
            f"{len(uncovered)} confirmed requirement{'s' if len(uncovered) != 1 else ''} lack tasks"
        )
    elif coverage < 0.85 and confirmed:
        score -= 6
        signals.append("Some confirmed requirements are still unlinked to tasks")
    if open_questions:
        score -= min(12, len(open_questions) * 4)
        signals.append(
            f"{len(open_questions)} open question{'s' if len(open_questions) != 1 else ''}"
        )
    if done_ratio >= 0.6:
        score += 8
        signals.append("Solid completion progress")
    if blocked == 0 and now <= 2 and coverage >= 0.7:
        score += 5

    score = max(0, min(100, score))

    if score >= 75:
        level = "healthy"
        summary = "Delivery looks steady. Keep clearing Now and watch blockers early."
    elif score >= 45:
        level = "at_risk"
        summary = "Delivery has friction. Resolve blockers and rebalance the active work."
    else:
        level = "critical"
        summary = "Delivery is stalled or unfocused. Run a check-in and approve a replan if needed."

    if not signals:
        signals.append("No major delivery risks detected")

    return DeliveryHealth(
        score=score,
        level=level,
        summary=summary,
        task_counts=counts,
        blocked_count=blocked,
        done_ratio=round(done_ratio, 3),
        requirement_coverage=round(coverage, 3),
        uncovered_confirmed_requirements=len(uncovered),
        open_question_count=len(open_questions),
        active_milestone_count=sum(
            1 for m in milestones if m.status == MilestoneStatus.ACTIVE
        ),
        signals=signals,
    )


def health_to_dict(health: DeliveryHealth) -> dict:
    return {
        "score": health.score,
        "level": health.level,
        "summary": health.summary,
        "task_counts": health.task_counts,
        "blocked_count": health.blocked_count,
        "done_ratio": health.done_ratio,
        "requirement_coverage": health.requirement_coverage,
        "uncovered_confirmed_requirements": health.uncovered_confirmed_requirements,
        "open_question_count": health.open_question_count,
        "active_milestone_count": health.active_milestone_count,
        "signals": health.signals,
    }


async def get_delivery_health(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> DeliveryHealth:
    await get_project_or_404(project_id, user_id, db)
    tasks = await list_tasks(db, project_id)
    milestones = await list_milestones(db, project_id)
    requirements, open_questions = await list_working_requirements(db, project_id)
    return compute_delivery_health(
        tasks=tasks,
        milestones=milestones,
        requirements=requirements,
        open_questions=open_questions,
    )


async def recent_activity_summary(
    db: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 12,
) -> str:
    events = await list_activity(db, project_id, limit=limit)
    if not events:
        return "No recent activity."
    lines = []
    for event in events:
        lines.append(f"- [{event.actor.value}] {event.summary}")
    return "\n".join(lines)
