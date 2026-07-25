from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_decision import DecisionCategory, DecisionStatus, ProjectDecision
from app.models.technology_exploration import TechnologyExploration
from app.schemas.decision import DecisionCreate, DecisionResponse, DecisionUpdate
from app.services.project_access import get_project_or_404


def decision_to_response(row: ProjectDecision) -> DecisionResponse:
    return DecisionResponse(
        id=row.id,
        project_id=row.project_id,
        technology_exploration_id=row.technology_exploration_id,
        title=row.title,
        category=row.category,
        status=row.status,
        context=row.context,
        chosen_option=row.chosen_option,
        alternatives_considered=row.alternatives_considered or [],
        rationale=row.rationale,
        consequences=row.consequences or [],
        related_requirement_ids=row.related_requirement_ids or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def get_decision_or_404(
    db: AsyncSession,
    project_id: UUID,
    decision_id: UUID,
) -> ProjectDecision:
    row = await db.get(ProjectDecision, decision_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


async def list_decisions(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> list[DecisionResponse]:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(ProjectDecision)
        .where(ProjectDecision.project_id == project_id)
        .order_by(ProjectDecision.created_at.desc())
    )
    return [decision_to_response(row) for row in result.scalars().all()]


async def create_decision(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    body: DecisionCreate,
) -> DecisionResponse:
    await get_project_or_404(project_id, user_id, db)

    if body.technology_exploration_id is not None:
        exploration = await db.get(
            TechnologyExploration, body.technology_exploration_id
        )
        if exploration is None or exploration.project_id != project_id:
            raise HTTPException(
                status_code=400,
                detail="Technology exploration not found for this project",
            )

    row = ProjectDecision(
        project_id=project_id,
        technology_exploration_id=body.technology_exploration_id,
        title=body.title.strip(),
        category=body.category,
        context=body.context,
        chosen_option=body.chosen_option.strip(),
        alternatives_considered=body.alternatives_considered,
        rationale=body.rationale,
        consequences=body.consequences,
        related_requirement_ids=body.related_requirement_ids,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return decision_to_response(row)


async def create_decision_from_exploration(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    exploration_id: UUID,
) -> DecisionResponse:
    await get_project_or_404(project_id, user_id, db)
    exploration = await db.get(TechnologyExploration, exploration_id)
    if exploration is None or exploration.project_id != project_id:
        raise HTTPException(status_code=404, detail="Technology exploration not found")

    analysis = exploration.analysis
    alternatives = [
        alt.get("name", "")
        for alt in analysis.get("alternatives", [])
        if alt.get("name")
    ]
    if analysis.get("recommended") and analysis["recommended"] not in alternatives:
        alternatives = [a for a in alternatives if a != analysis["recommended"]]

    body = DecisionCreate(
        title=f"Technology: {analysis.get('recommended', exploration.topic)[:200]}",
        category=DecisionCategory.TECHNOLOGY,
        context=exploration.topic,
        chosen_option=analysis.get("recommended", ""),
        alternatives_considered=alternatives,
        rationale=analysis.get("summary"),
        consequences=analysis.get("trade_offs", []),
        related_requirement_ids=analysis.get("requirements_addressed", []),
        technology_exploration_id=exploration.id,
    )
    return await create_decision(db, user_id, project_id, body)


async def update_decision(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    decision_id: UUID,
    body: DecisionUpdate,
) -> DecisionResponse:
    await get_project_or_404(project_id, user_id, db)
    row = await get_decision_or_404(db, project_id, decision_id)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)

    await db.commit()
    await db.refresh(row)
    return decision_to_response(row)


async def accept_decision(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    decision_id: UUID,
) -> DecisionResponse:
    return await update_decision(
        db,
        user_id,
        project_id,
        decision_id,
        DecisionUpdate(status=DecisionStatus.ACCEPTED),
    )
