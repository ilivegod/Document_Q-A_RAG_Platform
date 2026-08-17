"""Agency-wide project pipeline and capacity overview."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import PipelineStage, Project, ProjectStatus, ProjectType
from app.models.scope_change_request import ScopeChangeRequest, ScopeChangeStatus
from app.models.user import User
from app.services.delivery_health import get_delivery_health, health_to_dict


PIPELINE_ORDER: list[PipelineStage] = [
    PipelineStage.LEAD,
    PipelineStage.PROPOSAL_SENT,
    PipelineStage.IN_DEVELOPMENT,
    PipelineStage.QA_REVIEW,
    PipelineStage.HANDED_OFF,
]

PIPELINE_LABELS: dict[str, str] = {
    PipelineStage.LEAD.value: "Lead",
    PipelineStage.PROPOSAL_SENT.value: "Proposal sent",
    PipelineStage.IN_DEVELOPMENT.value: "In development",
    PipelineStage.QA_REVIEW.value: "QA / review",
    PipelineStage.HANDED_OFF.value: "Handed off",
}


@dataclass
class AgencyProjectSnapshot:
    id: UUID
    name: str
    client_name: str | None
    pipeline_stage: str
    health_score: int
    health_level: str
    health_summary: str
    blocked_count: int
    task_total: int
    pending_scope_changes: int


@dataclass
class AgencyOverview:
    projects: list[AgencyProjectSnapshot]
    projects_by_stage: dict[str, list[AgencyProjectSnapshot]]
    capacity_alerts: list[str]
    totals: dict[str, int]


async def _pending_scope_count(db: AsyncSession, project_id: UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(ScopeChangeRequest)
        .where(
            ScopeChangeRequest.project_id == project_id,
            ScopeChangeRequest.status == ScopeChangeStatus.PENDING_REVIEW,
        )
    )
    return int(result.scalar_one())


def _compute_capacity_alerts(snapshots: list[AgencyProjectSnapshot]) -> list[str]:
    alerts: list[str] = []
    in_dev = [
        s
        for s in snapshots
        if s.pipeline_stage == PipelineStage.IN_DEVELOPMENT.value
    ]
    blocked_in_dev = [s for s in in_dev if s.blocked_count > 0]
    critical = [s for s in snapshots if s.health_level == "critical"]
    at_risk = [s for s in snapshots if s.health_level == "at_risk"]
    pending_scope = [s for s in snapshots if s.pending_scope_changes > 0]

    if len(in_dev) > 3:
        alerts.append(
            f"{len(in_dev)} active engagements in development — watch capacity."
        )
    if blocked_in_dev:
        names = ", ".join(s.name for s in blocked_in_dev[:3])
        suffix = "…" if len(blocked_in_dev) > 3 else ""
        alerts.append(
            f"{len(blocked_in_dev)} in-development project(s) have blocked work: {names}{suffix}"
        )
    if critical:
        alerts.append(
            f"{len(critical)} project(s) in critical delivery health — prioritize check-ins."
        )
    if len(at_risk) >= 2:
        alerts.append(f"{len(at_risk)} projects are at risk across the portfolio.")
    if pending_scope:
        alerts.append(
            f"{sum(s.pending_scope_changes for s in pending_scope)} pending client scope "
            f"request(s) need review."
        )
    return alerts


async def get_agency_overview(db: AsyncSession, user: User) -> AgencyOverview:
    result = await db.execute(
        select(Project)
        .where(
            Project.user_id == user.id,
            Project.status == ProjectStatus.ACTIVE,
            Project.project_type == ProjectType.CLIENT,
        )
        .order_by(Project.updated_at.desc())
    )
    projects = list(result.scalars().all())

    snapshots: list[AgencyProjectSnapshot] = []
    for project in projects:
        health = await get_delivery_health(db, user.id, project.id)
        health_dict = health_to_dict(health)
        pending_scope = await _pending_scope_count(db, project.id)
        snapshots.append(
            AgencyProjectSnapshot(
                id=project.id,
                name=project.name,
                client_name=project.client_name,
                pipeline_stage=project.pipeline_stage.value,
                health_score=health_dict["score"],
                health_level=health_dict["level"],
                health_summary=health_dict["summary"],
                blocked_count=health_dict["blocked_count"],
                task_total=health_dict["task_counts"].get("total", 0),
                pending_scope_changes=pending_scope,
            )
        )

    by_stage: dict[str, list[AgencyProjectSnapshot]] = {
        stage.value: [] for stage in PIPELINE_ORDER
    }
    for snap in snapshots:
        by_stage.setdefault(snap.pipeline_stage, []).append(snap)

    totals = {
        "total_projects": len(snapshots),
        "in_development": len(
            [
                s
                for s in snapshots
                if s.pipeline_stage == PipelineStage.IN_DEVELOPMENT.value
            ]
        ),
        "at_risk": len(
            [s for s in snapshots if s.health_level in ("at_risk", "critical")]
        ),
        "blocked_total": sum(s.blocked_count for s in snapshots),
        "pending_scope_changes": sum(s.pending_scope_changes for s in snapshots),
    }

    return AgencyOverview(
        projects=snapshots,
        projects_by_stage=by_stage,
        capacity_alerts=_compute_capacity_alerts(snapshots),
        totals=totals,
    )
