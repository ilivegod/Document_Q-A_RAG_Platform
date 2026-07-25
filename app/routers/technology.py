from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.technology import (
    TechnologyExploreCreate,
    TechnologyExplorationResponse,
)
from app.services.project_access import get_project_or_404
from app.services.technology_explorer import (
    explore_technology,
    list_technology_explorations,
)

router = APIRouter(
    prefix="/projects/{project_id}/technology",
    tags=["technology"],
)


@router.get("", response_model=list[TechnologyExplorationResponse])
async def get_technology_explorations(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_technology_explorations(db, current_user.id, project_id)


@router.post("/explore", response_model=TechnologyExplorationResponse)
async def explore_project_technology(
    project_id: UUID,
    body: TechnologyExploreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    return await explore_technology(
        db, current_user.id, project_id, body.topic.strip()
    )
