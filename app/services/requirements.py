from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import (
    Requirement,
    RequirementCategory,
    RequirementPriority,
)
from app.schemas.requirement import RequirementResponse, SourceRef


def _source_refs_from_json(raw: Any) -> list[SourceRef]:
    if not raw:
        return []
    return [SourceRef.model_validate(item) for item in raw]


def requirement_to_response(req: Requirement) -> RequirementResponse:
    return RequirementResponse(
        id=req.id,
        project_id=req.project_id,
        baseline_id=req.baseline_id,
        stable_id=req.stable_id,
        title=req.title,
        description=req.description,
        category=req.category,
        priority=req.priority,
        status=req.status,
        acceptance_criteria=req.acceptance_criteria or [],
        assumptions=req.assumptions or [],
        source_refs=_source_refs_from_json(req.source_refs),
        sort_order=req.sort_order,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


async def list_working_requirements(
    db: AsyncSession,
    project_id: UUID,
) -> tuple[list[Requirement], list[Requirement]]:
    """Return (requirements, open_questions) for the working set."""
    result = await db.execute(
        select(Requirement)
        .where(
            Requirement.project_id == project_id,
            Requirement.baseline_id.is_(None),
        )
        .order_by(Requirement.sort_order.asc(), Requirement.stable_id.asc())
    )
    rows = result.scalars().all()
    requirements = [r for r in rows if r.category != RequirementCategory.OPEN_QUESTION]
    open_questions = [r for r in rows if r.category == RequirementCategory.OPEN_QUESTION]
    return requirements, open_questions


async def get_requirement_or_404(
    db: AsyncSession,
    project_id: UUID,
    requirement_id: UUID,
) -> Requirement:
    from fastapi import HTTPException

    req = await db.get(Requirement, requirement_id)
    if (
        req is None
        or req.project_id != project_id
        or req.baseline_id is not None
    ):
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


async def next_stable_id(db: AsyncSession, project_id: UUID, prefix: str = "REQ") -> str:
    result = await db.execute(
        select(Requirement.stable_id).where(
            Requirement.project_id == project_id,
            Requirement.baseline_id.is_(None),
            Requirement.stable_id.like(f"{prefix}-%"),
        )
    )
    existing = result.scalars().all()
    max_num = 0
    for sid in existing:
        try:
            num = int(sid.split("-")[-1])
            max_num = max(max_num, num)
        except ValueError:
            continue
    return f"{prefix}-{max_num + 1:03d}"


async def next_question_stable_id(db: AsyncSession, project_id: UUID) -> str:
    return await next_stable_id(db, project_id, prefix="Q")


def _map_category(value: str) -> RequirementCategory:
    try:
        return RequirementCategory(value)
    except ValueError:
        return RequirementCategory.FEATURE


def _map_priority(value: str) -> RequirementPriority:
    try:
        return RequirementPriority(value)
    except ValueError:
        return RequirementPriority.UNKNOWN
