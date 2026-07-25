from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.decision import DecisionCreate, DecisionResponse, DecisionUpdate
from app.services.decisions import (
    accept_decision,
    create_decision,
    create_decision_from_exploration,
    list_decisions,
    update_decision,
)

router = APIRouter(prefix="/projects/{project_id}/decisions", tags=["decisions"])


@router.get("", response_model=list[DecisionResponse])
async def get_decisions(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_decisions(db, current_user.id, project_id)


@router.post("", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def post_decision(
    project_id: UUID,
    body: DecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_decision(db, current_user.id, project_id, body)


@router.post(
    "/from-exploration/{exploration_id}",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_decision_from_exploration(
    project_id: UUID,
    exploration_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_decision_from_exploration(
        db, current_user.id, project_id, exploration_id
    )


@router.patch("/{decision_id}", response_model=DecisionResponse)
async def patch_decision(
    project_id: UUID,
    decision_id: UUID,
    body: DecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_decision(
        db, current_user.id, project_id, decision_id, body
    )


@router.post("/{decision_id}/accept", response_model=DecisionResponse)
async def post_accept_decision(
    project_id: UUID,
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await accept_decision(db, current_user.id, project_id, decision_id)
