"""SOW document persistence and response helpers."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sow_document import SowDocument, SowGenerationStatus, SowStatus
from app.schemas.sow import SowDocumentResponse, SowTierResponse
from app.services.sow_generator import (
    _compute_tier_cost,
    generate_sow_token,
)


def _tier_dict_to_response(tier: dict) -> SowTierResponse:
    return SowTierResponse(
        tier_key=str(tier.get("tier_key", "")),
        tier_name=str(tier.get("tier_name", "")),
        description=str(tier.get("description", "") or ""),
        total_hours=float(tier.get("total_hours", 0)),
        total_cost=float(tier.get("total_cost", 0)),
        requirement_ids=list(tier.get("requirement_ids") or []),
        estimated_weeks=int(tier.get("estimated_weeks", 4) or 4),
        contingency_applied=bool(tier.get("contingency_applied", False)),
    )


def sow_to_response(sow: SowDocument) -> SowDocumentResponse:
    tiers_raw = sow.tiers if isinstance(sow.tiers, list) else []
    return SowDocumentResponse(
        id=sow.id,
        project_id=sow.project_id,
        hourly_rate=Decimal(str(sow.hourly_rate)),
        deposit_percentage=Decimal(str(sow.deposit_percentage)),
        tiers=[_tier_dict_to_response(t) for t in tiers_raw],
        out_of_scope_items=list(sow.out_of_scope_items or []),
        labor_breakdown=sow.labor_breakdown if isinstance(sow.labor_breakdown, list) else None,
        summary=sow.summary,
        status=sow.status.value,
        generation_status=sow.generation_status.value,
        accepted_tier_key=sow.accepted_tier_key,
        accepted_at=sow.accepted_at,
        created_at=sow.created_at,
        updated_at=sow.updated_at,
    )


async def get_latest_sow(
    db: AsyncSession,
    project_id: UUID,
) -> SowDocument | None:
    result = await db.execute(
        select(SowDocument)
        .where(SowDocument.project_id == project_id)
        .order_by(SowDocument.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_sow(db: AsyncSession, project_id: UUID) -> SowDocument:
    sow = await get_latest_sow(db, project_id)
    if sow is not None:
        return sow

    sow = SowDocument(
        project_id=project_id,
        token=generate_sow_token(),
        tiers=[],
        out_of_scope_items=[],
        status=SowStatus.DRAFT,
        generation_status=SowGenerationStatus.IDLE,
    )
    db.add(sow)
    await db.flush()
    return sow


def recalculate_tier_costs(sow: SowDocument) -> None:
    hourly_rate = Decimal(str(sow.hourly_rate))
    tiers = sow.tiers if isinstance(sow.tiers, list) else []
    updated: list[dict] = []
    for tier in tiers:
        item = dict(tier)
        hours = float(item.get("total_hours", 0))
        item["total_cost"] = float(_compute_tier_cost(hours, hourly_rate))
        updated.append(item)
    sow.tiers = updated


def public_sow_visible(sow: SowDocument) -> bool:
    return sow.status in (SowStatus.SENT, SowStatus.ACCEPTED)


async def get_sow_for_portal(
    db: AsyncSession,
    project_id: UUID,
) -> SowDocument:
    sow = await get_latest_sow(db, project_id)
    if sow is None or not public_sow_visible(sow):
        raise HTTPException(
            status_code=404,
            detail="No proposal is available for review yet.",
        )
    return sow
