"""Internal SOW configuration and generation routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.activity_event import ActivityActor
from app.models.project import PipelineStage, Project
from app.models.sow_document import SowGenerationStatus, SowStatus
from app.models.user import User
from app.schemas.sow import (
    PortalLinkResponse,
    SowDocumentResponse,
    SowDocumentUpdate,
)
from app.services.execution import record_activity
from app.services.portal_service import (
    ensure_portal_access,
    hash_portal_passcode,
    portal_passcode_required,
    rotate_portal_token,
)
from app.services.project_access import get_project_or_404
from app.services.sow_service import (
    get_or_create_sow,
    recalculate_tier_costs,
    sow_to_response,
)
from app.workers.tasks import generate_sow_task

router = APIRouter(prefix="/projects/{project_id}/sow", tags=["sow"])


def _portal_url(token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/p/{token}"


@router.get("", response_model=SowDocumentResponse)
async def get_sow(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    sow = await get_or_create_sow(db, project_id)
    await db.commit()
    await db.refresh(sow)
    return sow_to_response(sow)


@router.patch("", response_model=SowDocumentResponse)
async def update_sow(
    project_id: UUID,
    body: SowDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    sow = await get_or_create_sow(db, project_id)

    if sow.status == SowStatus.ACCEPTED and body.tiers is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit tiers after the client has accepted a proposal.",
        )

    if body.hourly_rate is not None:
        sow.hourly_rate = body.hourly_rate
    if body.deposit_percentage is not None:
        sow.deposit_percentage = body.deposit_percentage
    if body.out_of_scope_items is not None:
        sow.out_of_scope_items = body.out_of_scope_items
    if body.tiers is not None:
        if sow.status != SowStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Tiers can only be edited while the SOW is in draft status.",
            )
        sow.tiers = body.tiers

    if body.hourly_rate is not None or body.tiers is not None:
        recalculate_tier_costs(sow)

    if body.passcode is not None:
        access = await ensure_portal_access(db, project_id)
        if body.passcode == "":
            access.passcode_hash = None
        else:
            access.passcode_hash = hash_portal_passcode(body.passcode)

    await db.commit()
    await db.refresh(sow)
    return sow_to_response(sow)


@router.post("/generate", response_model=SowDocumentResponse)
async def generate_sow(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    sow = await get_or_create_sow(db, project_id)

    if sow.generation_status == SowGenerationStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="SOW generation is already in progress.",
        )

    sow.generation_status = SowGenerationStatus.RUNNING
    await db.commit()

    generate_sow_task.delay(
        str(sow.id),
        str(current_user.id),
        str(project_id),
    )
    await db.refresh(sow)
    return sow_to_response(sow)


@router.post("/send", response_model=SowDocumentResponse)
async def send_sow(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, current_user.id, db)
    sow = await get_or_create_sow(db, project_id)

    tiers = sow.tiers if isinstance(sow.tiers, list) else []
    if not tiers:
        raise HTTPException(
            status_code=400,
            detail="Generate or configure SOW tiers before sending to the client.",
        )
    if sow.generation_status == SowGenerationStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Wait for SOW generation to finish before sending.",
        )

    sow.status = SowStatus.SENT
    project.pipeline_stage = PipelineStage.PROPOSAL_SENT

    await record_activity(
        db,
        project_id,
        summary="Statement of Work sent to client",
        event_type="sow.sent",
        actor=ActivityActor.USER,
        entity_type="sow_document",
        entity_id=sow.id,
    )
    await db.commit()
    await db.refresh(sow)
    return sow_to_response(sow)


@router.post("/portal-link", response_model=PortalLinkResponse)
async def create_portal_link(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    access = await ensure_portal_access(db, project_id)
    await db.commit()
    return PortalLinkResponse(
        token=access.token,
        portal_url=_portal_url(access.token),
        passcode_required=portal_passcode_required(access),
    )


@router.post("/portal-link/rotate", response_model=PortalLinkResponse)
async def rotate_portal_link(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    access = await rotate_portal_token(db, project_id)
    await db.commit()
    return PortalLinkResponse(
        token=access.token,
        portal_url=_portal_url(access.token),
        passcode_required=portal_passcode_required(access),
    )
