from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.requirement_baseline import RequirementBaseline
from app.models.user import User
from app.schemas.baseline import ApproveBaselineRequest, BaselineResponse
from app.services.project_access import get_project_or_404
from app.services.requirements_extractor import approve_baseline, get_current_baseline

router = APIRouter(prefix="/projects/{project_id}/baselines", tags=["baselines"])


@router.get("", response_model=list[BaselineResponse])
async def list_baselines(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    result = await db.execute(
        select(RequirementBaseline)
        .where(RequirementBaseline.project_id == project_id)
        .order_by(RequirementBaseline.version.desc())
    )
    baselines = result.scalars().all()
    return [
        BaselineResponse(
            id=b.id,
            project_id=b.project_id,
            version=b.version,
            status=b.status,
            label=b.label,
            snapshot=b.snapshot,
            approved_at=b.approved_at,
            created_at=b.created_at,
        )
        for b in baselines
    ]


@router.get("/current", response_model=BaselineResponse | None)
async def get_current_approved_baseline(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_current_baseline(db, current_user.id, project_id)


@router.post("/approve", response_model=BaselineResponse)
async def approve_project_baseline(
    project_id: UUID,
    body: ApproveBaselineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await approve_baseline(
        db, current_user.id, project_id, label=body.label
    )
