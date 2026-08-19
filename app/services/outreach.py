"""Outreach email drafting and Resend domain-backed sending."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import resend
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.prospect import (
    OutreachDomainStatus,
    OutreachEmail,
    OutreachEmailStatus,
    Prospect,
    ProspectStatus,
    UserOutreachSettings,
)
from app.services.llm_errors import raise_llm_http_error

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


class OutreachDraft(BaseModel):
    subject: str = Field(description="Short email subject line")
    body_text: str = Field(description="Plain-text email body")
    body_html: str = Field(description="HTML email body")


async def get_or_create_outreach_settings(
    db: AsyncSession,
    user_id: UUID,
) -> UserOutreachSettings:
    settings_row = await db.get(UserOutreachSettings, user_id)
    if settings_row:
        return settings_row
    settings_row = UserOutreachSettings(user_id=user_id)
    db.add(settings_row)
    await db.flush()
    return settings_row


def _map_domain_status(status: str | None) -> OutreachDomainStatus:
    mapping = {
        "not_started": OutreachDomainStatus.PENDING,
        "pending": OutreachDomainStatus.PENDING,
        "verified": OutreachDomainStatus.VERIFIED,
        "failed": OutreachDomainStatus.FAILED,
    }
    return mapping.get(status or "", OutreachDomainStatus.PENDING)


def _create_domain_sync(domain_name: str) -> dict[str, Any]:
    return resend.Domains.create({"name": domain_name})


def _get_domain_sync(domain_id: str) -> dict[str, Any]:
    return resend.Domains.get(domain_id)


def _verify_domain_sync(domain_id: str) -> dict[str, Any]:
    return resend.Domains.verify(domain_id)


def _send_outreach_sync(
    from_address: str,
    to: str,
    subject: str,
    html: str,
    text: str,
) -> dict[str, Any]:
    return resend.Emails.send(
        {
            "from": from_address,
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
        }
    )


async def start_domain_verification(
    db: AsyncSession,
    user_id: UUID,
    domain_name: str,
) -> UserOutreachSettings:
    row = await get_or_create_outreach_settings(db, user_id)
    result = await asyncio.to_thread(_create_domain_sync, domain_name.strip().lower())
    row.domain_name = domain_name.strip().lower()
    row.resend_domain_id = result.get("id")
    row.domain_status = _map_domain_status(result.get("status"))
    row.dns_records = result.get("records") or []
    return row


async def refresh_domain_status(
    db: AsyncSession,
    user_id: UUID,
) -> UserOutreachSettings:
    row = await get_or_create_outreach_settings(db, user_id)
    if not row.resend_domain_id:
        row.domain_status = OutreachDomainStatus.NOT_CONFIGURED
        return row

    result = await asyncio.to_thread(_get_domain_sync, row.resend_domain_id)
    row.domain_status = _map_domain_status(result.get("status"))
    row.dns_records = result.get("records") or row.dns_records
    return row


async def trigger_domain_verify(
    db: AsyncSession,
    user_id: UUID,
) -> UserOutreachSettings:
    row = await get_or_create_outreach_settings(db, user_id)
    if not row.resend_domain_id:
        return row
    await asyncio.to_thread(_verify_domain_sync, row.resend_domain_id)
    return await refresh_domain_status(db, user_id)


async def count_sends_today(db: AsyncSession, user_id: UUID) -> int:
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        select(func.count())
        .select_from(OutreachEmail)
        .where(
            OutreachEmail.user_id == user_id,
            OutreachEmail.status == OutreachEmailStatus.SENT,
            OutreachEmail.sent_at >= today_start,
        )
    )
    return int(result.scalar_one())


async def draft_outreach_email(
    prospect: Prospect,
    settings_row: UserOutreachSettings,
    sender_name: str | None = None,
) -> OutreachDraft:
    prompt = PromptTemplate.from_template(
        """Write a short, human cold email for a boutique dev agency.

Business: {business_name}
Pitch angle: {pitch_angle}
Fit summary: {fit_summary}
Sender name: {sender_name}
Signature (optional): {signature}

Rules:
- 80-120 words, conversational, no hype
- One clear CTA (15-minute call)
- Include plain signature if provided
- Return subject, body_text, and simple HTML body (no external images)"""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(OutreachDraft)

    try:
        return await (prompt | model).ainvoke(
            {
                "business_name": prospect.business_name,
                "pitch_angle": prospect.pitch_angle or "Digital upgrade opportunity",
                "fit_summary": prospect.fit_summary or "",
                "sender_name": sender_name or settings_row.from_name or "Agency partner",
                "signature": settings_row.signature_block or "",
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="draft outreach email")


async def send_outreach_email(
    db: AsyncSession,
    email: OutreachEmail,
    settings_row: UserOutreachSettings,
) -> OutreachEmail:
    if email.status != OutreachEmailStatus.APPROVED:
        raise ValueError("Email must be approved before sending")

    if settings_row.domain_status != OutreachDomainStatus.VERIFIED:
        raise ValueError("Outreach domain is not verified")

    if not settings_row.from_email or not settings_row.from_name:
        raise ValueError("From name and email are required")

    prospect = await db.get(Prospect, email.prospect_id)
    if not prospect or not prospect.contact_email:
        raise ValueError("Prospect contact email is required")

    sends_today = await count_sends_today(db, email.user_id)
    if sends_today >= settings.outreach_daily_send_limit:
        raise ValueError(
            f"Daily outreach limit reached ({settings.outreach_daily_send_limit})"
        )

    from_address = f"{settings_row.from_name} <{settings_row.from_email}>"

    try:
        result = await asyncio.to_thread(
            _send_outreach_sync,
            from_address,
            prospect.contact_email,
            email.subject,
            email.body_html,
            email.body_text,
        )
        email.status = OutreachEmailStatus.SENT
        email.resend_message_id = result.get("id")
        email.sent_at = datetime.now(timezone.utc)
        email.error_message = None
        prospect.status = ProspectStatus.CONTACTED
    except Exception as exc:
        logger.exception("Failed to send outreach email %s", email.id)
        email.status = OutreachEmailStatus.FAILED
        email.error_message = str(exc)[:2000]

    return email
