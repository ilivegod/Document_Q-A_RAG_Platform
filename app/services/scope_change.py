"""Scope change request persistence and review actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityActor
from app.models.scope_change_request import ScopeChangeRequest, ScopeChangeStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.scope_change import ScopeChangeResponse
from app.services.execution import record_activity
from app.services.project_access import get_project_or_404
from app.services.scope_change_evaluator import evaluate_scope_change

logger = logging.getLogger(__name__)


def scope_change_to_response(row: ScopeChangeRequest) -> ScopeChangeResponse:
    return ScopeChangeResponse(
        id=row.id,
        project_id=row.project_id,
        client_description=row.client_description,
        ai_is_out_of_scope=row.ai_is_out_of_scope,
        ai_reasoning=row.ai_reasoning,
        estimated_hours=Decimal(str(row.estimated_hours)) if row.estimated_hours else None,
        estimated_cost=Decimal(str(row.estimated_cost)) if row.estimated_cost else None,
        status=row.status.value,
        linked_task_id=row.linked_task_id,
        linked_requirement_id=row.linked_requirement_id,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


async def list_scope_changes(
    db: AsyncSession,
    project_id: UUID,
    status: ScopeChangeStatus | None = None,
) -> list[ScopeChangeRequest]:
    stmt = (
        select(ScopeChangeRequest)
        .where(ScopeChangeRequest.project_id == project_id)
        .order_by(ScopeChangeRequest.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(ScopeChangeRequest.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_scope_change_or_404(
    db: AsyncSession,
    project_id: UUID,
    request_id: UUID,
) -> ScopeChangeRequest:
    row = await db.get(ScopeChangeRequest, request_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scope change request not found")
    return row


async def submit_client_scope_change(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    description: str,
) -> ScopeChangeRequest:
    evaluation, estimated_hours, estimated_cost = await evaluate_scope_change(
        db, project_id, user_id, description
    )

    row = ScopeChangeRequest(
        project_id=project_id,
        client_description=description.strip(),
        ai_is_out_of_scope=evaluation.is_out_of_scope,
        ai_reasoning=evaluation.reasoning.strip(),
        estimated_hours=estimated_hours,
        estimated_cost=estimated_cost,
        status=ScopeChangeStatus.PENDING_REVIEW,
    )
    db.add(row)
    await db.flush()

    await record_activity(
        db,
        project_id,
        summary="Client submitted a scope change request",
        event_type="scope_change.submitted",
        actor=ActivityActor.SYSTEM,
        entity_type="scope_change_request",
        entity_id=row.id,
        payload={
            "is_out_of_scope": evaluation.is_out_of_scope,
            "estimated_hours": float(estimated_hours) if estimated_hours else None,
        },
    )
    return row


async def decide_scope_change(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    request_id: UUID,
    action: str,
) -> ScopeChangeRequest:
    await get_project_or_404(project_id, user_id, db)
    row = await get_scope_change_or_404(db, project_id, request_id)

    if row.status != ScopeChangeStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be reviewed",
        )

    now = datetime.now(timezone.utc)

    if action == "reject":
        row.status = ScopeChangeStatus.REJECTED
        row.reviewed_at = now
        await record_activity(
            db,
            project_id,
            summary="Rejected client scope change request",
            event_type="scope_change.rejected",
            actor=ActivityActor.USER,
            entity_type="scope_change_request",
            entity_id=row.id,
        )
        await db.commit()
        await db.refresh(row)
        return row

    if action == "approve_change_order":
        row.status = ScopeChangeStatus.APPROVED_CHANGE_ORDER
        row.reviewed_at = now
        await record_activity(
            db,
            project_id,
            summary="Approved scope change as change order",
            event_type="scope_change.approved",
            actor=ActivityActor.USER,
            entity_type="scope_change_request",
            entity_id=row.id,
        )
        await db.commit()
        await db.refresh(row)
        return row

    if action == "convert_to_task":
        title = row.client_description.strip()
        if len(title) > 120:
            title = title[:117] + "..."

        task = Task(
            project_id=project_id,
            title=title,
            description=row.client_description,
            status=TaskStatus.NEXT,
            priority=TaskPriority.SHOULD,
            estimate_hours=float(row.estimated_hours) if row.estimated_hours else None,
        )
        db.add(task)
        await db.flush()

        row.status = ScopeChangeStatus.CONVERTED_TO_TASK
        row.linked_task_id = task.id
        row.reviewed_at = now

        await record_activity(
            db,
            project_id,
            summary=f"Converted scope change to task “{task.title}”",
            event_type="scope_change.converted",
            actor=ActivityActor.USER,
            entity_type="scope_change_request",
            entity_id=row.id,
            payload={"task_id": str(task.id)},
        )
        await db.commit()
        await db.refresh(row)
        return row

    raise HTTPException(
        status_code=400,
        detail="action must be approve_change_order, reject, or convert_to_task",
    )
