"""Outreach settings, domain verification, and email draft/send."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.dependencies.rate_limit import (
    OUTREACH_SEND_LIMIT,
    get_user_id_key,
    limiter,
)
from app.models.prospect import OutreachEmail, OutreachEmailStatus
from app.models.user import User
from app.schemas.prospect import (
    OutreachDomainCreate,
    OutreachEmailResponse,
    OutreachEmailUpdate,
    OutreachSettingsResponse,
    OutreachSettingsUpdate,
)
from app.services.outreach import (
    count_sends_today,
    draft_outreach_email,
    get_or_create_outreach_settings,
    refresh_domain_status,
    send_outreach_email,
    start_domain_verification,
    trigger_domain_verify,
)
from app.services.prospect_service import get_prospect_or_404

router = APIRouter(tags=["outreach"])


def _email_to_response(email: OutreachEmail) -> OutreachEmailResponse:
    return OutreachEmailResponse(
        id=email.id,
        prospect_id=email.prospect_id,
        subject=email.subject,
        body_html=email.body_html,
        body_text=email.body_text,
        status=email.status,
        resend_message_id=email.resend_message_id,
        error_message=email.error_message,
        created_at=email.created_at,
        sent_at=email.sent_at,
    )


@router.get("/outreach/settings", response_model=OutreachSettingsResponse)
async def get_outreach_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await get_or_create_outreach_settings(db, current_user.id)
    sends_today = await count_sends_today(db, current_user.id)
    await db.commit()
    return OutreachSettingsResponse(
        from_name=row.from_name,
        from_email=row.from_email,
        domain_name=row.domain_name,
        domain_status=row.domain_status,
        dns_records=row.dns_records,
        signature_block=row.signature_block,
        daily_send_limit=settings.outreach_daily_send_limit,
        sends_today=sends_today,
    )


@router.patch("/outreach/settings", response_model=OutreachSettingsResponse)
async def update_outreach_settings(
    body: OutreachSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = await get_or_create_outreach_settings(db, current_user.id)
    if body.from_name is not None:
        row.from_name = body.from_name
    if body.from_email is not None:
        row.from_email = body.from_email
    if body.signature_block is not None:
        row.signature_block = body.signature_block
    sends_today = await count_sends_today(db, current_user.id)
    await db.commit()
    await db.refresh(row)
    return OutreachSettingsResponse(
        from_name=row.from_name,
        from_email=row.from_email,
        domain_name=row.domain_name,
        domain_status=row.domain_status,
        dns_records=row.dns_records,
        signature_block=row.signature_block,
        daily_send_limit=settings.outreach_daily_send_limit,
        sends_today=sends_today,
    )


@router.post("/outreach/domain", response_model=OutreachSettingsResponse)
async def create_outreach_domain(
    body: OutreachDomainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        row = await start_domain_verification(db, current_user.id, body.domain_name)
        sends_today = await count_sends_today(db, current_user.id)
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return OutreachSettingsResponse(
        from_name=row.from_name,
        from_email=row.from_email,
        domain_name=row.domain_name,
        domain_status=row.domain_status,
        dns_records=row.dns_records,
        signature_block=row.signature_block,
        daily_send_limit=settings.outreach_daily_send_limit,
        sends_today=sends_today,
    )


@router.get("/outreach/domain/status", response_model=OutreachSettingsResponse)
async def get_outreach_domain_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        row = await refresh_domain_status(db, current_user.id)
        sends_today = await count_sends_today(db, current_user.id)
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return OutreachSettingsResponse(
        from_name=row.from_name,
        from_email=row.from_email,
        domain_name=row.domain_name,
        domain_status=row.domain_status,
        dns_records=row.dns_records,
        signature_block=row.signature_block,
        daily_send_limit=settings.outreach_daily_send_limit,
        sends_today=sends_today,
    )


@router.post("/outreach/domain/verify", response_model=OutreachSettingsResponse)
async def verify_outreach_domain(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        row = await trigger_domain_verify(db, current_user.id)
        sends_today = await count_sends_today(db, current_user.id)
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return OutreachSettingsResponse(
        from_name=row.from_name,
        from_email=row.from_email,
        domain_name=row.domain_name,
        domain_status=row.domain_status,
        dns_records=row.dns_records,
        signature_block=row.signature_block,
        daily_send_limit=settings.outreach_daily_send_limit,
        sends_today=sends_today,
    )


@router.post(
    "/prospects/{prospect_id}/outreach/draft",
    response_model=OutreachEmailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_outreach_draft(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prospect = await get_prospect_or_404(prospect_id, current_user.id, db)
    settings_row = await get_or_create_outreach_settings(db, current_user.id)
    draft = await draft_outreach_email(prospect, settings_row, current_user.username)

    email = OutreachEmail(
        user_id=current_user.id,
        prospect_id=prospect.id,
        subject=draft.subject,
        body_html=draft.body_html,
        body_text=draft.body_text,
        status=OutreachEmailStatus.DRAFT,
    )
    db.add(email)
    await db.commit()
    await db.refresh(email)
    return _email_to_response(email)


@router.get(
    "/prospects/{prospect_id}/outreach/emails",
    response_model=list[OutreachEmailResponse],
)
async def list_outreach_emails(
    prospect_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_prospect_or_404(prospect_id, current_user.id, db)
    result = await db.execute(
        select(OutreachEmail)
        .where(
            OutreachEmail.prospect_id == prospect_id,
            OutreachEmail.user_id == current_user.id,
        )
        .order_by(OutreachEmail.created_at.desc())
    )
    return [_email_to_response(e) for e in result.scalars().all()]


@router.patch("/outreach/emails/{email_id}", response_model=OutreachEmailResponse)
async def update_outreach_email(
    email_id: UUID,
    body: OutreachEmailUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    email = await db.get(OutreachEmail, email_id)
    if not email or email.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Email not found")
    if email.status == OutreachEmailStatus.SENT:
        raise HTTPException(status_code=400, detail="Sent emails cannot be edited")

    if body.subject is not None:
        email.subject = body.subject
    if body.body_html is not None:
        email.body_html = body.body_html
    if body.body_text is not None:
        email.body_text = body.body_text
    if body.status is not None:
        if body.status not in (
            OutreachEmailStatus.DRAFT,
            OutreachEmailStatus.APPROVED,
        ):
            raise HTTPException(status_code=400, detail="Invalid status transition")
        email.status = body.status

    await db.commit()
    await db.refresh(email)
    return _email_to_response(email)


@router.post("/outreach/emails/{email_id}/send", response_model=OutreachEmailResponse)
@limiter.limit(OUTREACH_SEND_LIMIT, key_func=get_user_id_key)
async def send_outreach_email_route(
    request: Request,
    email_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    email = await db.get(OutreachEmail, email_id)
    if not email or email.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Email not found")

    if email.status != OutreachEmailStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Approve the email before sending",
        )

    settings_row = await get_or_create_outreach_settings(db, current_user.id)
    try:
        email = await send_outreach_email(db, email, settings_row)
        await db.commit()
        await db.refresh(email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _email_to_response(email)
