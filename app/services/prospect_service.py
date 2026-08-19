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
from app.services.prospect_discovery import (
    MAX_CANDIDATES,
    enrich_place_candidate,
    fetch_place_candidates,
)
from app.services.prospect_fit import score_prospect_fit
from app.services.website_audit import audit_website

logger = logging.getLogger(__name__)


async def _append_progress(
    db: AsyncSession,
    search: ProspectSearch,
    message: str,
    step: str | None = None,
) -> None:
    log = list(search.progress_log or [])
    log.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "step": step,
        }
    )
    search.progress_log = log
    search.current_step = message
    await db.commit()


async def _refresh_cancel_flag(db: AsyncSession, search_id: UUID) -> bool:
    result = await db.execute(
        select(ProspectSearch.cancel_requested).where(ProspectSearch.id == search_id)
    )
    row = result.scalar_one_or_none()
    return bool(row)


async def run_prospect_discovery(search_id: str) -> None:
    from app.database import async_session

    async with async_session() as db:
        search = await db.get(ProspectSearch, UUID(search_id))
        if not search:
            logger.error("Prospect search %s not found", search_id)
            return

        search.status = ProspectSearchStatus.RUNNING
        search.progress_log = []
        search.current_step = None
        search.cancel_requested = False
        await db.commit()

        created = 0

        try:
            await _append_progress(
                db,
                search,
                f"Starting search for “{search.industry_keywords}” in {search.location_query}.",
                "start",
            )
            await _append_progress(
                db,
                search,
                f"Querying Google Places (up to {MAX_CANDIDATES} businesses)…",
                "places_query",
            )

            candidates = await fetch_place_candidates(
                search.location_query,
                search.industry_keywords,
                search.radius_km,
            )

            if not candidates:
                await _append_progress(
                    db,
                    search,
                    "No businesses found for this query.",
                    "no_results",
                )
                search.status = ProspectSearchStatus.COMPLETE
                search.result_count = 0
                search.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            await _append_progress(
                db,
                search,
                f"Found {len(candidates)} candidate(s). Reviewing each business…",
                "candidates_found",
            )

            for index, candidate in enumerate(candidates, start=1):
                if await _refresh_cancel_flag(db, search.id):
                    await _append_progress(
                        db,
                        search,
                        f"Stop requested — finishing after {created} saved lead(s).",
                        "cancelled",
                    )
                    search.status = ProspectSearchStatus.CANCELLED
                    search.result_count = created
                    search.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return

                name_preview = candidate.get("business_name", "Business")
                await _append_progress(
                    db,
                    search,
                    f"[{index}/{len(candidates)}] Reviewing {name_preview}…",
                    "review_business",
                )

                existing = await db.execute(
                    select(Prospect.id).where(
                        Prospect.user_id == search.user_id,
                        Prospect.place_id == candidate["place_id"],
                    )
                )
                if existing.scalar_one_or_none():
                    await _append_progress(
                        db,
                        search,
                        f"Skipped {name_preview} — already in your lead list.",
                        "skip_duplicate",
                    )
                    continue

                await _append_progress(
                    db,
                    search,
                    f"Fetching details for {name_preview}…",
                    "place_details",
                )
                place = await enrich_place_candidate(
                    candidate["place_id"],
                    candidate["business_name"],
                    candidate.get("address"),
                )

                website_url = place.get("website_url")
                await _append_progress(
                    db,
                    search,
                    f"Auditing website for {place['business_name']}…",
                    "website_audit",
                )
                audit = await audit_website(website_url)

                if search.filter_no_website and audit.website_status != WebsiteStatus.NONE:
                    await _append_progress(
                        db,
                        search,
                        f"Skipped {place['business_name']} — has a website (filter: no website only).",
                        "skip_filter",
                    )
                    continue
                if search.filter_poor_website and audit.website_status not in (
                    WebsiteStatus.NONE,
                    WebsiteStatus.POOR,
                ):
                    await _append_progress(
                        db,
                        search,
                        f"Skipped {place['business_name']} — website not poor enough for filters.",
                        "skip_filter",
                    )
                    continue

                await _append_progress(
                    db,
                    search,
                    f"Extracting contact email for {place['business_name']}…",
                    "contact_extract",
                )
                contact_email = extract_contact_email_from_pages(
                    audit.homepage_html,
                    audit.contact_html or None,
                    website_url,
                )

                await _append_progress(
                    db,
                    search,
                    f"Scoring fit for {place['business_name']} with AI…",
                    "fit_score",
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
                search.result_count = created
                await db.commit()

                await _append_progress(
                    db,
                    search,
                    f"Added lead: {place['business_name']} (fit score {fit.fit_score}). "
                    f"Total saved: {created}.",
                    "lead_saved",
                )

                if await _refresh_cancel_flag(db, search.id):
                    await _append_progress(
                        db,
                        search,
                        f"Stop requested — search ended with {created} lead(s) saved.",
                        "cancelled",
                    )
                    search.status = ProspectSearchStatus.CANCELLED
                    search.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return

            search.status = ProspectSearchStatus.COMPLETE
            search.result_count = created
            search.completed_at = datetime.now(timezone.utc)
            search.error_message = None
            await _append_progress(
                db,
                search,
                f"Search complete — {created} lead(s) saved to your account.",
                "complete",
            )
        except Exception as exc:
            logger.exception("Prospect search %s failed", search_id)
            search = await db.get(ProspectSearch, UUID(search_id))
            if search:
                search.status = ProspectSearchStatus.FAILED
                search.error_message = str(exc)[:2000]
                search.completed_at = datetime.now(timezone.utc)
                await _append_progress(
                    db,
                    search,
                    f"Search failed: {str(exc)[:500]}",
                    "failed",
                )


async def cancel_prospect_search(search_id: UUID, user_id: UUID, db: AsyncSession) -> ProspectSearch:
    from fastapi import HTTPException

    search = await db.get(ProspectSearch, search_id)
    if not search or search.user_id != user_id:
        raise HTTPException(status_code=404, detail="Search not found")
    if search.status not in (
        ProspectSearchStatus.PENDING,
        ProspectSearchStatus.RUNNING,
    ):
        raise HTTPException(status_code=400, detail="Search is not active")
    search.cancel_requested = True
    await db.commit()
    await db.refresh(search)
    return search


async def get_active_prospect_search(
    user_id: UUID,
    db: AsyncSession,
) -> ProspectSearch | None:
    result = await db.execute(
        select(ProspectSearch)
        .where(
            ProspectSearch.user_id == user_id,
            ProspectSearch.status.in_(
                [
                    ProspectSearchStatus.PENDING,
                    ProspectSearchStatus.RUNNING,
                ]
            ),
        )
        .order_by(ProspectSearch.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


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
