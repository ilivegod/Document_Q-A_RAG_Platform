"""Read-only delivery dashboard for client portal."""

from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.release import ReleaseStatus
from app.services.delivery import list_releases
from app.services.delivery_health import get_delivery_health, health_to_dict
from app.services.execution import list_milestones


async def get_client_dashboard(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> dict:
    health = await get_delivery_health(db, user_id, project_id)
    health_dict = health_to_dict(health)

    milestones = await list_milestones(db, project_id)
    milestone_items = [
        {
            "title": m.title,
            "status": m.status.value,
            "target_date": m.target_date.isoformat() if m.target_date else None,
        }
        for m in milestones
    ]

    releases = await list_releases(db, project_id)
    published = [
        r
        for r in releases
        if r.status == ReleaseStatus.PUBLISHED
    ]
    published.sort(
        key=lambda r: r.published_at or r.created_at,
        reverse=True,
    )
    release_items = [
        {
            "version": r.version,
            "title": r.title,
            "notes": (r.notes or "")[:500] or None,
            "published_at": (
                r.published_at.isoformat() if r.published_at else None
            ),
        }
        for r in published[:5]
    ]

    # Client-friendly health label without internal task breakdown
    level_labels = {
        "healthy": "On track",
        "at_risk": "Needs attention",
        "critical": "At risk",
        "not_started": "Starting soon",
    }

    return {
        "health": {
            "score": health_dict["score"],
            "level": health_dict["level"],
            "label": level_labels.get(health_dict["level"], health_dict["level"]),
            "summary": health_dict["summary"],
            "active_milestones": health_dict["active_milestone_count"],
            "completion_ratio": health_dict["done_ratio"],
        },
        "milestones": milestone_items,
        "recent_releases": release_items,
    }
