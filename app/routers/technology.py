from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.technology import (
    ProjectTechnologyCreate,
    ProjectTechnologyResponse,
    TechnologyCatalogItemResponse,
    TechnologyStackResponse,
)
from app.services.project_access import get_project_or_404
from app.services.technology_stack import (
    add_technology_to_stack,
    generate_project_stack,
    list_project_stack,
    remove_technology_from_stack,
    search_technology_catalog,
)

router = APIRouter(tags=["technology"])


@router.get(
    "/projects/{project_id}/technology",
    response_model=TechnologyStackResponse,
)
async def get_project_technology_stack(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_project_stack(db, current_user.id, project_id)


@router.post(
    "/projects/{project_id}/technology/generate",
    response_model=TechnologyStackResponse,
)
async def generate_technology_stack(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    await generate_project_stack(db, current_user.id, project_id)
    return await list_project_stack(db, current_user.id, project_id)


@router.post(
    "/projects/{project_id}/technology",
    response_model=ProjectTechnologyResponse,
    status_code=201,
)
async def add_project_technology(
    project_id: UUID,
    body: ProjectTechnologyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await add_technology_to_stack(db, current_user.id, project_id, body)


@router.delete("/projects/{project_id}/technology/{item_id}", status_code=204)
async def delete_project_technology(
    project_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await remove_technology_from_stack(db, current_user.id, project_id, item_id)
    return None


@router.get("/technology/catalog", response_model=list[TechnologyCatalogItemResponse])
async def search_catalog(
    query: str = Query(default="", max_length=200),
    current_user: User = Depends(get_current_user),
):
    return search_technology_catalog(query)
