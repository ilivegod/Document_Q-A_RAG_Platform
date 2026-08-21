"""Prospect discovery pipeline orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
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
from app.services.prospect_fit_heuristic import score_prospect_fit_heuristic
from app.services.website_audit import audit_website

logger = logging.getLogger(__name__)

STALE_PENDING_MINUTES = 2
STALE_RUNNING_MINUTES = 10


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


async def reconcile_stale_prospect_searches(user_id: UUID, db: AsyncSession) -> None:
    """Mark abandoned searches failed so users can start a new one."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ProspectSearch).where(
            ProspectSearch.user_id == user_id,
            ProspectSearch.status.in_(
                [
                    ProspectSearchStatus.PENDING,
                    ProspectSearchStatus.RUNNING,
                ]
            ),
        )
    )
    stale = False
    for search in result.scalars().all():
        created = search.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_minutes = (now - created).total_seconds() / 60
        if search.status == ProspectSearchStatus.PENDING and age_minutes > STALE_PENDING_MINUTES:
            search.status = ProspectSearchStatus.FAILED
            search.error_message = (
                "Search did not start. Ensure the Celery worker is running and retry."
            )
            search.completed_at = now
            stale = True
        elif search.status == ProspectSearchStatus.RUNNING and age_minutes > STALE_RUNNING_MINUTES:
            search.status = ProspectSearchStatus.FAILED
            search.error_message = "Search timed out before completion."
            search.completed_at = now
            stale = True
    if stale:
        await db.commit()


async def mark_prospect_search_failed(search_id: str, error_message: str) -> None:
    """Update search status using a fresh engine (safe for Celery retries)."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            search = await db.get(ProspectSearch, UUID(search_id))
            if not search:
                return
            if search.status in (
                ProspectSearchStatus.COMPLETE,
                ProspectSearchStatus.CANCELLED,
            ):
                return
            search.status = ProspectSearchStatus.FAILED
            search.error_message = error_message[:2000]
            search.completed_at = datetime.now(timezone.utc)
            await _append_progress(
                db,
                search,
                f"Search failed: {error_message[:500]}",
                "failed",
            )
    finally:
        await engine.dispose()


async def _run_prospect_discovery_with_session(db: AsyncSession, search_id: str) -> None:
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
    skipped_duplicate = 0
    skipped_filter = 0

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
                skipped_duplicate += 1
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

            if search.filter_no_website or search.filter_poor_website:
                matches_no_website = (
                    search.filter_no_website
                    and audit.website_status == WebsiteStatus.NONE
                )
                matches_poor_website = (
                    search.filter_poor_website
                    and audit.website_status
                    in (WebsiteStatus.NONE, WebsiteStatus.POOR)
                )
                if not (matches_no_website or matches_poor_website):
                    skipped_filter += 1
                    if search.filter_no_website and search.filter_poor_website:
                        skip_reason = "doesn't match filters (no website or poor website)."
                    elif search.filter_no_website:
                        skip_reason = "has a website (filter: no website only)."
                    else:
                        skip_reason = "website not poor enough (filter: poor website only)."
                    await _append_progress(
                        db,
                        search,
                        f"Skipped {place['business_name']} — {skip_reason}",
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
                f"Calculating fit score for {place['business_name']}…",
                "fit_score",
            )
            fit = score_prospect_fit_heuristic(
                business_name=place["business_name"],
                industry_keywords=search.industry_keywords,
                website_status=audit.website_status,
                audit_signals=audit.audit_signals,
            )

            audit_payload = dict(audit.audit_signals or {})
            if audit.homepage_text:
                audit_payload["homepage_excerpt"] = audit.homepage_text[:2000]

            prospect = Prospect(
                user_id=search.user_id,
                search_id=search.id,
                place_id=place["place_id"],
                business_name=place["business_name"],
                address=place.get("address"),
                phone=place.get("phone"),
                website_url=website_url,
                website_status=audit.website_status,
                audit_signals=audit_payload,
                fit_score=fit.fit_score,
                fit_summary=fit.fit_summary,
                pitch_angle=fit.pitch_angle or None,
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
        reviewed = len(candidates)
        summary_parts = [
            f"Search complete — {created} lead(s) saved.",
            f"Reviewed {reviewed} business{'es' if reviewed != 1 else ''}.",
        ]
        if skipped_filter:
            summary_parts.append(f"{skipped_filter} skipped by filters.")
        if skipped_duplicate:
            summary_parts.append(f"{skipped_duplicate} already in your list.")
        if created == 0 and reviewed > 0 and (
            search.filter_no_website or search.filter_poor_website
        ):
            summary_parts.append(
                "Tip: turn off website filters for a broader list."
            )
        await _append_progress(
            db,
            search,
            " ".join(summary_parts),
            "complete",
        )
    except Exception as exc:
        logger.exception("Prospect search %s failed", search_id)
        search.status = ProspectSearchStatus.FAILED
        search.error_message = str(exc)[:2000]
        search.completed_at = datetime.now(timezone.utc)
        await _append_progress(
            db,
            search,
            f"Search failed: {str(exc)[:500]}",
            "failed",
        )
        raise


async def run_prospect_discovery(search_id: str) -> None:
    """Celery task entrypoint — uses a per-task DB engine (safe after worker fork)."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            await _run_prospect_discovery_with_session(db, search_id)
    finally:
        await engine.dispose()


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
    await reconcile_stale_prospect_searches(user_id, db)
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


async def score_prospect_with_ai(
    prospect_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Prospect:
    """Optional LLM fit refresh — one Gemini call per user action."""
    prospect = await get_prospect_or_404(prospect_id, user_id, db)
    industry_keywords = "local business"
    niche_notes = None
    if prospect.search_id:
        search = await db.get(ProspectSearch, prospect.search_id)
        if search:
            industry_keywords = search.industry_keywords
            niche_notes = search.niche_notes

    homepage_text = ""
    if prospect.audit_signals and isinstance(
        prospect.audit_signals.get("homepage_excerpt"), str
    ):
        homepage_text = prospect.audit_signals["homepage_excerpt"]
    elif prospect.website_url:
        audit = await audit_website(prospect.website_url)
        homepage_text = audit.homepage_text

    fit = await score_prospect_fit(
        business_name=prospect.business_name,
        industry_keywords=industry_keywords,
        website_status=prospect.website_status,
        audit_signals=prospect.audit_signals,
        homepage_text=homepage_text,
        niche_notes=niche_notes,
    )

    prospect.fit_score = fit.fit_score
    prospect.fit_summary = fit.fit_summary
    prospect.pitch_angle = fit.pitch_angle or None
    await db.commit()
    await db.refresh(prospect)
    return prospect


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
