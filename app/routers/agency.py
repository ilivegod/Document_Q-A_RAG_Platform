"""Agency portfolio overview."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.agency import AgencyOverviewResponse, AgencyProjectSnapshotResponse
from app.services.agency_overview import get_agency_overview

router = APIRouter(prefix="/agency", tags=["agency"])


@router.get("/overview", response_model=AgencyOverviewResponse)
async def agency_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overview = await get_agency_overview(db, current_user)
    project_responses = [
        AgencyProjectSnapshotResponse(
            id=s.id,
            name=s.name,
            client_name=s.client_name,
            pipeline_stage=s.pipeline_stage,
            health_score=s.health_score,
            health_level=s.health_level,
            health_summary=s.health_summary,
            blocked_count=s.blocked_count,
            task_total=s.task_total,
            pending_scope_changes=s.pending_scope_changes,
        )
        for s in overview.projects
    ]
    by_stage = {
        stage: [
            AgencyProjectSnapshotResponse(
                id=s.id,
                name=s.name,
                client_name=s.client_name,
                pipeline_stage=s.pipeline_stage,
                health_score=s.health_score,
                health_level=s.health_level,
                health_summary=s.health_summary,
                blocked_count=s.blocked_count,
                task_total=s.task_total,
                pending_scope_changes=s.pending_scope_changes,
            )
            for s in items
        ]
        for stage, items in overview.projects_by_stage.items()
    }
    return AgencyOverviewResponse(
        projects=project_responses,
        projects_by_stage=by_stage,
        capacity_alerts=overview.capacity_alerts,
        totals=overview.totals,
    )
