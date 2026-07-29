from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.requirement import (
    ExtractMergeSummaryResponse,
    ExtractRequirementsResponse,
    RequirementResponse,
    RequirementUpdate,
    RequirementsListResponse,
)
from app.services.project_access import get_project_or_404
from app.services.requirements import (
    get_requirement_or_404,
    list_working_requirements,
    requirement_to_response,
)
from app.services.requirements_extractor import extract_requirements_for_project

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("", response_model=RequirementsListResponse)
async def list_requirements(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    requirements, open_questions = await list_working_requirements(db, project_id)
    return RequirementsListResponse(
        requirements=[requirement_to_response(r) for r in requirements],
        open_questions=[requirement_to_response(q) for q in open_questions],
    )


@router.post("/extract", response_model=ExtractRequirementsResponse)
async def extract_requirements(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _touched, ambiguities, contradictions, summary = (
        await extract_requirements_for_project(db, current_user.id, project_id)
    )
    requirements, open_questions = await list_working_requirements(db, project_id)
    return ExtractRequirementsResponse(
        requirements=[requirement_to_response(r) for r in requirements],
        open_questions=[requirement_to_response(q) for q in open_questions],
        ambiguities=ambiguities,
        contradictions=contradictions,
        merge=ExtractMergeSummaryResponse(
            added=summary.added,
            updated=summary.updated,
            preserved=summary.preserved,
        ),
    )


@router.patch("/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(
    project_id: UUID,
    requirement_id: UUID,
    body: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    req = await get_requirement_or_404(db, project_id, requirement_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(req, field, value)
    await db.commit()
    await db.refresh(req)
    return requirement_to_response(req)


@router.delete("/{requirement_id}", status_code=204)
async def delete_requirement(
    project_id: UUID,
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    req = await get_requirement_or_404(db, project_id, requirement_id)
    await db.delete(req)
    await db.commit()
    return None
