from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.change_request import ChangeRequestCreate, ChangeRequestResponse
from app.services.change_impact import analyze_change_request, list_change_requests
from app.services.project_access import get_project_or_404

router = APIRouter(
    prefix="/projects/{project_id}/change-requests",
    tags=["change-requests"],
)


@router.get("", response_model=list[ChangeRequestResponse])
async def get_change_requests(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_change_requests(db, current_user.id, project_id)


@router.post("/analyze", response_model=ChangeRequestResponse)
async def analyze_change(
    project_id: UUID,
    body: ChangeRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    return await analyze_change_request(
        db, current_user.id, project_id, body.request_text
    )
