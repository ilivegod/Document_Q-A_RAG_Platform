"""Public client portal routes (token auth, no JWT)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.rate_limit import limiter
from app.models.activity_event import ActivityActor
from app.models.project import PipelineStage
from app.models.sow_document import SowStatus
from app.schemas.sow import (
    PublicPortalMetaResponse,
    PublicSowResponse,
    SowAcceptRequest,
    SowAcceptResponse,
    SowTierResponse,
)
from app.services.execution import record_activity
from app.services.portal_service import (
    get_portal_access_by_token,
    get_project_for_portal,
    portal_passcode_required,
    verify_portal_passcode,
)
from app.services.sow_service import (
    get_latest_sow,
    get_sow_for_portal,
    sow_to_response,
)

router = APIRouter(prefix="/public/portal", tags=["public-portal"])

PORTAL_READ_LIMIT = "60/minute"
PORTAL_ACCEPT_LIMIT = "10/hour"


def _tiers_to_public(sow) -> list[SowTierResponse]:
    return sow_to_response(sow).tiers


@router.get("/{token}", response_model=PublicPortalMetaResponse)
@limiter.limit(PORTAL_READ_LIMIT)
async def get_portal_meta(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    access = await get_portal_access_by_token(db, token)
    project = await get_project_for_portal(db, access)
    sow = await get_latest_sow(db, project.id)
    sow_status = sow.status.value if sow is not None else None
    return PublicPortalMetaResponse(
        project_name=project.name,
        client_name=project.client_name,
        passcode_required=portal_passcode_required(access),
        sow_status=sow_status,
    )


@router.get("/{token}/sow", response_model=PublicSowResponse)
@limiter.limit(PORTAL_READ_LIMIT)
async def get_public_sow(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    access = await get_portal_access_by_token(db, token)
    project = await get_project_for_portal(db, access)
    sow = await get_sow_for_portal(db, project.id)
    return PublicSowResponse(
        summary=sow.summary,
        tiers=_tiers_to_public(sow),
        out_of_scope_items=list(sow.out_of_scope_items or []),
        status=sow.status.value,
        accepted_tier_key=sow.accepted_tier_key,
        deposit_percentage=sow.deposit_percentage,
        hourly_rate=sow.hourly_rate,
    )


@router.post("/{token}/sow/accept", response_model=SowAcceptResponse)
@limiter.limit(PORTAL_ACCEPT_LIMIT)
async def accept_public_sow(
    request: Request,
    token: str,
    body: SowAcceptRequest,
    db: AsyncSession = Depends(get_db),
):
    access = await get_portal_access_by_token(db, token)
    if not verify_portal_passcode(access, body.passcode):
        raise HTTPException(status_code=403, detail="Invalid or missing portal passcode")

    project = await get_project_for_portal(db, access)
    sow = await get_sow_for_portal(db, project.id)

    if sow.status == SowStatus.ACCEPTED and sow.accepted_tier_key:
        return SowAcceptResponse(
            accepted_tier_key=sow.accepted_tier_key,
            status=sow.status.value,
            message="This proposal was already accepted.",
        )

    if sow.status != SowStatus.SENT:
        raise HTTPException(
            status_code=400,
            detail="This proposal is not open for acceptance.",
        )

    tiers = sow.tiers if isinstance(sow.tiers, list) else []
    tier_keys = {str(t.get("tier_key")) for t in tiers}
    if body.tier_key not in tier_keys:
        raise HTTPException(status_code=400, detail="Invalid tier selection.")

    sow.status = SowStatus.ACCEPTED
    sow.accepted_tier_key = body.tier_key
    sow.accepted_at = datetime.now(timezone.utc)
    project.pipeline_stage = PipelineStage.IN_DEVELOPMENT

    await record_activity(
        db,
        project.id,
        summary=f"Client accepted SOW tier “{body.tier_key}”",
        event_type="sow.accepted",
        actor=ActivityActor.SYSTEM,
        entity_type="sow_document",
        entity_id=sow.id,
        payload={"tier_key": body.tier_key},
    )
    await db.commit()

    return SowAcceptResponse(
        accepted_tier_key=body.tier_key,
        status=sow.status.value,
        message="Thank you — your selection has been recorded.",
    )
