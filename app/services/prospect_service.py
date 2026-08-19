"""Prospect discovery pipeline orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect import (
    Prospect,
    ProspectSearch,
    ProspectSearchStatus,
    ProspectStatus,
    WebsiteStatus,
)
from app.services.contact_extraction import extract_contact_email_from_pages
from app.services.prospect_discovery import search_places
from app.services.prospect_fit import score_prospect_fit
from app.services.website_audit import audit_website

logger = logging.getLogger(__name__)


async def run_prospect_discovery(search_id: str) -> None:
    from app.database import async_session

    async with async_session() as db:
        search = await db.get(ProspectSearch, UUID(search_id))
        if not search:
            logger.error("Prospect search %s not found", search_id)
            return

        search.status = ProspectSearchStatus.RUNNING
        await db.commit()

        try:
            places = await search_places(
                search.location_query,
                search.industry_keywords,
                search.radius_km,
            )
            created = 0

            for place in places:
                existing = await db.execute(
                    select(Prospect.id).where(
                        Prospect.user_id == search.user_id,
                        Prospect.place_id == place["place_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                website_url = place.get("website_url")
                audit = await audit_website(website_url)

                if search.filter_no_website and audit.website_status != WebsiteStatus.NONE:
                    continue
                if search.filter_poor_website and audit.website_status not in (
                    WebsiteStatus.NONE,
                    WebsiteStatus.POOR,
                ):
                    continue

                contact_email = extract_contact_email_from_pages(
                    audit.homepage_html,
                    audit.contact_html or None,
                    website_url,
                )

                fit = await score_prospect_fit(
                    business_name=place["business_name"],
                    industry_keywords=search.industry_keywords,
                    website_status=audit.website_status,
                    audit_signals=audit.audit_signals,
                    homepage_text=audit.homepage_text,
                    niche_notes=search.niche_notes,
                )

                prospect = Prospect(
                    user_id=search.user_id,
                    search_id=search.id,
                    place_id=place["place_id"],
                    business_name=place["business_name"],
                    address=place.get("address"),
                    phone=place.get("phone"),
                    website_url=website_url,
                    website_status=audit.website_status,
                    audit_signals=audit.audit_signals,
                    fit_score=fit.fit_score,
                    fit_summary=fit.fit_summary,
                    pitch_angle=fit.pitch_angle,
                    contact_email=contact_email,
                    status=ProspectStatus.NEW,
                )
                db.add(prospect)
                created += 1

            search.status = ProspectSearchStatus.COMPLETE
            search.result_count = created
            search.completed_at = datetime.now(timezone.utc)
            search.error_message = None
            await db.commit()
        except Exception as exc:
            logger.exception("Prospect search %s failed", search_id)
            search.status = ProspectSearchStatus.FAILED
            search.error_message = str(exc)[:2000]
            search.completed_at = datetime.now(timezone.utc)
            await db.commit()


async def get_prospect_or_404(
    prospect_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Prospect:
    from fastapi import HTTPException

    prospect = await db.get(Prospect, prospect_id)
    if not prospect or prospect.user_id != user_id:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect
