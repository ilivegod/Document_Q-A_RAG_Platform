"""Internal scope change review routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.scope_change_request import ScopeChangeStatus
from app.models.user import User
from app.schemas.scope_change import ScopeChangeDecide, ScopeChangeResponse
from app.services.project_access import get_project_or_404
from app.services.scope_change import (
    decide_scope_change,
    list_scope_changes,
    scope_change_to_response,
)

router = APIRouter(
    prefix="/projects/{project_id}/scope-changes",
    tags=["scope-changes"],
)


@router.get("", response_model=list[ScopeChangeResponse])
async def get_scope_changes(
    project_id: UUID,
    status: ScopeChangeStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    rows = await list_scope_changes(db, project_id, status=status)
    return [scope_change_to_response(r) for r in rows]


@router.patch("/{request_id}", response_model=ScopeChangeResponse)
async def review_scope_change(
    project_id: UUID,
    request_id: UUID,
    body: ScopeChangeDecide,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await decide_scope_change(
        db,
        current_user.id,
        project_id,
        request_id,
        body.action,
    )
    return scope_change_to_response(row)
