"""QA / release / handoff services for the delivery loop."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity_event import ActivityActor
from app.models.handoff import Handoff, HandoffStatus
from app.models.project import Project
from app.models.qa_run import QaCheckItem, QaItemStatus, QaRun, QaRunStatus
from app.models.release import Release, ReleaseStatus
from app.models.requirement import RequirementStatus
from app.models.task import TaskStatus
from app.schemas.delivery import (
    HandoffResponse,
    QaCheckItemResponse,
    QaRunResponse,
    ReleaseResponse,
)
from app.services.pipeline_stage import advance_to_handed_off, advance_to_qa_review
from app.services.execution import list_decisions, list_tasks, record_activity
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404
from app.services.requirements import list_working_requirements

logger = logging.getLogger(__name__)


# --- helpers ---


def _item_counts(items: list[QaCheckItem]) -> dict[str, int]:
    counts = {status.value: 0 for status in QaItemStatus}
    for item in items:
        counts[item.status.value] = counts.get(item.status.value, 0) + 1
    counts["total"] = len(items)
    return counts


def qa_item_to_response(item: QaCheckItem) -> QaCheckItemResponse:
    return QaCheckItemResponse(
        id=item.id,
        qa_run_id=item.qa_run_id,
        requirement_id=item.requirement_id,
        task_id=item.task_id,
        title=item.title,
        description=item.description,
        status=item.status.value,
        evidence_note=item.evidence_note,
        sort_order=item.sort_order,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def qa_run_to_response(
    run: QaRun, items: list[QaCheckItem] | None = None
) -> QaRunResponse:
    items = items or []
    return QaRunResponse(
        id=run.id,
        project_id=run.project_id,
        title=run.title,
        status=run.status.value,
        notes=run.notes,
        item_counts=_item_counts(items),
        items=[qa_item_to_response(item) for item in items],
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


def release_to_response(release: Release) -> ReleaseResponse:
    changelog = release.changelog or []
    if not isinstance(changelog, list):
        changelog = []
    return ReleaseResponse(
        id=release.id,
        project_id=release.project_id,
        qa_run_id=release.qa_run_id,
        version=release.version,
        title=release.title,
        status=release.status.value,
        notes=release.notes,
        changelog=changelog,
        created_at=release.created_at,
        updated_at=release.updated_at,
        published_at=release.published_at,
    )


def handoff_to_response(handoff: Handoff) -> HandoffResponse:
    payload = handoff.payload or {}
    if not isinstance(payload, dict):
        payload = {}
    return HandoffResponse(
        id=handoff.id,
        project_id=handoff.project_id,
        release_id=handoff.release_id,
        title=handoff.title,
        status=handoff.status.value,
        summary=handoff.summary,
        payload=payload,
        created_at=handoff.created_at,
        updated_at=handoff.updated_at,
        finalized_at=handoff.finalized_at,
    )


def _map_qa_run_status(value: str) -> QaRunStatus:
    try:
        return QaRunStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid QA run status: {value}") from exc


def _map_qa_item_status(value: str) -> QaItemStatus:
    try:
        return QaItemStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid QA item status: {value}") from exc


def _map_release_status(value: str) -> ReleaseStatus:
    try:
        return ReleaseStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid release status: {value}") from exc


def _map_handoff_status(value: str) -> HandoffStatus:
    try:
        return HandoffStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid handoff status: {value}") from exc


def recompute_qa_run_status(run: QaRun, items: list[QaCheckItem]) -> None:
    if not items:
        run.status = QaRunStatus.DRAFT
        run.completed_at = None
        return

    statuses = {item.status for item in items}
    if QaItemStatus.FAILED in statuses:
        run.status = QaRunStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        return

    if statuses <= {QaItemStatus.PASSED, QaItemStatus.SKIPPED}:
        run.status = QaRunStatus.PASSED
        run.completed_at = datetime.now(timezone.utc)
        return

    if QaItemStatus.PENDING in statuses and statuses == {QaItemStatus.PENDING}:
        run.status = QaRunStatus.DRAFT
        run.completed_at = None
        return

    run.status = QaRunStatus.IN_PROGRESS
    run.completed_at = None


# --- list / get ---


async def list_qa_runs(db: AsyncSession, project_id: UUID) -> list[QaRun]:
    result = await db.execute(
        select(QaRun)
        .where(QaRun.project_id == project_id)
        .order_by(QaRun.created_at.desc())
    )
    return list(result.scalars().all())


async def list_qa_items(db: AsyncSession, qa_run_id: UUID) -> list[QaCheckItem]:
    result = await db.execute(
        select(QaCheckItem)
        .where(QaCheckItem.qa_run_id == qa_run_id)
        .order_by(QaCheckItem.sort_order.asc(), QaCheckItem.created_at.asc())
    )
    return list(result.scalars().all())


async def get_qa_run_or_404(
    db: AsyncSession, project_id: UUID, qa_run_id: UUID
) -> QaRun:
    result = await db.execute(
        select(QaRun).where(QaRun.id == qa_run_id, QaRun.project_id == project_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="QA run not found")
    return run


async def get_qa_item_or_404(
    db: AsyncSession, qa_run_id: UUID, item_id: UUID
) -> QaCheckItem:
    result = await db.execute(
        select(QaCheckItem).where(
            QaCheckItem.id == item_id, QaCheckItem.qa_run_id == qa_run_id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="QA check item not found")
    return item


async def list_releases(db: AsyncSession, project_id: UUID) -> list[Release]:
    result = await db.execute(
        select(Release)
        .where(Release.project_id == project_id)
        .order_by(Release.created_at.desc())
    )
    return list(result.scalars().all())


async def get_release_or_404(
    db: AsyncSession, project_id: UUID, release_id: UUID
) -> Release:
    result = await db.execute(
        select(Release).where(
            Release.id == release_id, Release.project_id == project_id
        )
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(status_code=404, detail="Release not found")
    return release


async def list_handoffs(db: AsyncSession, project_id: UUID) -> list[Handoff]:
    result = await db.execute(
        select(Handoff)
        .where(Handoff.project_id == project_id)
        .order_by(Handoff.created_at.desc())
    )
    return list(result.scalars().all())


async def get_handoff_or_404(
    db: AsyncSession, project_id: UUID, handoff_id: UUID
) -> Handoff:
    result = await db.execute(
        select(Handoff).where(
            Handoff.id == handoff_id, Handoff.project_id == project_id
        )
    )
    handoff = result.scalar_one_or_none()
    if handoff is None:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return handoff


def build_changelog(tasks) -> list[dict[str, Any]]:
    entries = []
    for task in tasks:
        if task.status != TaskStatus.DONE:
            continue
        entries.append(
            {
                "task_id": str(task.id),
                "title": task.title,
                "priority": task.priority.value,
                "requirement_id": str(task.requirement_id)
                if task.requirement_id
                else None,
            }
        )
    return entries


async def build_coverage(db: AsyncSession, project_id: UUID) -> dict[str, Any]:
    requirements, open_questions = await list_working_requirements(db, project_id)
    confirmed = [r for r in requirements if r.status == RequirementStatus.CONFIRMED]
    tasks = await list_tasks(db, project_id)
    done = [t for t in tasks if t.status == TaskStatus.DONE]
    covered_req_ids = {t.requirement_id for t in tasks if t.requirement_id}
    uncovered = [r for r in confirmed if r.id not in covered_req_ids]

    qa_runs = await list_qa_runs(db, project_id)
    latest_passed = next(
        (run for run in qa_runs if run.status == QaRunStatus.PASSED), None
    )
    releases = await list_releases(db, project_id)
    published = [r for r in releases if r.status == ReleaseStatus.PUBLISHED]
    handoffs = await list_handoffs(db, project_id)
    finals = [h for h in handoffs if h.status == HandoffStatus.FINAL]

    return {
        "confirmed_requirements": len(confirmed),
        "uncovered_confirmed_requirements": len(uncovered),
        "open_questions": len(open_questions),
        "tasks_total": len(tasks),
        "tasks_done": len(done),
        "qa_runs": len(qa_runs),
        "has_passed_qa": latest_passed is not None,
        "releases_published": len(published),
        "handoffs_final": len(finals),
    }


async def build_handoff_payload(
    db: AsyncSession,
    project_id: UUID,
    release: Release | None,
) -> dict[str, Any]:
    coverage = await build_coverage(db, project_id)
    requirements, open_questions = await list_working_requirements(db, project_id)
    decisions = await list_decisions(db, project_id)
    tasks = await list_tasks(db, project_id)
    blocked = [t for t in tasks if t.status == TaskStatus.BLOCKED]

    return {
        "coverage": coverage,
        "release": {
            "id": str(release.id),
            "version": release.version,
            "title": release.title,
            "status": release.status.value,
        }
        if release
        else None,
        "unresolved_open_questions": [
            {"id": str(q.id), "stable_id": q.stable_id, "title": q.title}
            for q in open_questions
        ],
        "blocked_tasks": [
            {"id": str(t.id), "title": t.title, "blocker_reason": t.blocker_reason}
            for t in blocked
        ],
        "active_decisions": [
            {"id": str(d.id), "title": d.title}
            for d in decisions
            if d.status.value == "active"
        ],
        "confirmed_requirements": [
            {
                "id": str(r.id),
                "stable_id": r.stable_id,
                "title": r.title,
                "priority": r.priority.value,
            }
            for r in requirements
            if r.status == RequirementStatus.CONFIRMED
        ],
    }


# --- create / update ---


def seed_items_from_requirements(requirements) -> list[tuple[Any, str, str | None]]:
    """Return (requirement, title, description) tuples for checklist seeding."""
    seeded: list[tuple[Any, str, str | None]] = []
    for req in requirements:
        if req.status != RequirementStatus.CONFIRMED:
            continue
        criteria = req.acceptance_criteria or []
        if isinstance(criteria, list) and criteria:
            for criterion in criteria:
                text = str(criterion).strip()
                if not text:
                    continue
                seeded.append((req, text[:500], f"From {req.stable_id}: {req.title}"))
        else:
            seeded.append(
                (
                    req,
                    f"Verify: {req.title}"[:500],
                    req.description,
                )
            )
    return seeded


async def create_qa_run(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    title: str,
    notes: str | None = None,
    seed_from_requirements: bool = True,
) -> tuple[QaRun, list[QaCheckItem]]:
    project = await get_project_or_404(project_id, user_id, db)
    run = QaRun(
        project_id=project_id,
        title=title.strip()[:500],
        notes=notes,
        status=QaRunStatus.DRAFT,
    )
    db.add(run)
    await db.flush()

    items: list[QaCheckItem] = []
    if seed_from_requirements:
        requirements, _ = await list_working_requirements(db, project_id)
        for index, (req, item_title, description) in enumerate(
            seed_items_from_requirements(requirements)
        ):
            item = QaCheckItem(
                qa_run_id=run.id,
                requirement_id=req.id,
                title=item_title,
                description=description,
                status=QaItemStatus.PENDING,
                sort_order=index,
            )
            db.add(item)
            items.append(item)

    await record_activity(
        db,
        project_id,
        summary=f"Created QA run “{run.title}” ({len(items)} checks)",
        event_type="qa_run.created",
        actor=ActivityActor.USER,
        entity_type="qa_run",
        entity_id=run.id,
        payload={"item_count": len(items)},
    )
    advance_to_qa_review(project)
    await db.commit()
    await db.refresh(run)
    items = await list_qa_items(db, run.id)
    return run, items


async def update_qa_run(
    db: AsyncSession,
    project_id: UUID,
    run: QaRun,
    *,
    title: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> QaRun:
    if title is not None:
        run.title = title.strip()[:500]
    if notes is not None:
        run.notes = notes
    if status is not None:
        mapped = _map_qa_run_status(status)
        run.status = mapped
        if mapped in {QaRunStatus.PASSED, QaRunStatus.FAILED}:
            run.completed_at = datetime.now(timezone.utc)
        else:
            run.completed_at = None
        if mapped == QaRunStatus.IN_PROGRESS:
            project = await db.get(Project, project_id)
            if project is not None:
                advance_to_qa_review(project)

    await record_activity(
        db,
        project_id,
        summary=f"Updated QA run “{run.title}”",
        event_type="qa_run.updated",
        actor=ActivityActor.USER,
        entity_type="qa_run",
        entity_id=run.id,
    )
    await db.commit()
    await db.refresh(run)
    return run


async def update_qa_item(
    db: AsyncSession,
    project_id: UUID,
    run: QaRun,
    item: QaCheckItem,
    *,
    status: str | None = None,
    evidence_note: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> tuple[QaRun, list[QaCheckItem]]:
    if status is not None:
        item.status = _map_qa_item_status(status)
    if evidence_note is not None:
        item.evidence_note = evidence_note
    if title is not None:
        item.title = title.strip()[:500]
    if description is not None:
        item.description = description

    items = await list_qa_items(db, run.id)
    recompute_qa_run_status(run, items)

    await record_activity(
        db,
        project_id,
        summary=f"Marked QA check “{item.title}” as {item.status.value}",
        event_type="qa_item.updated",
        actor=ActivityActor.USER,
        entity_type="qa_check_item",
        entity_id=item.id,
        payload={"status": item.status.value, "qa_run_id": str(run.id)},
    )
    await db.commit()
    await db.refresh(run)
    items = await list_qa_items(db, run.id)
    return run, items


async def delete_qa_run(db: AsyncSession, project_id: UUID, run: QaRun) -> None:
    title = run.title
    run_id = run.id
    await db.delete(run)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted QA run “{title}”",
        event_type="qa_run.deleted",
        actor=ActivityActor.USER,
        entity_type="qa_run",
        entity_id=run_id,
    )
    await db.commit()


async def create_release(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    version: str,
    title: str,
    qa_run_id: UUID | None = None,
    notes: str | None = None,
) -> Release:
    await get_project_or_404(project_id, user_id, db)
    if qa_run_id is not None:
        await get_qa_run_or_404(db, project_id, qa_run_id)

    tasks = await list_tasks(db, project_id)
    changelog = build_changelog(tasks)
    release = Release(
        project_id=project_id,
        qa_run_id=qa_run_id,
        version=version.strip()[:64],
        title=title.strip()[:500],
        notes=notes,
        changelog=changelog,
        status=ReleaseStatus.DRAFT,
    )
    db.add(release)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Created release draft {release.version}",
        event_type="release.created",
        actor=ActivityActor.USER,
        entity_type="release",
        entity_id=release.id,
        payload={"done_tasks": len(changelog)},
    )
    await db.commit()
    await db.refresh(release)
    return release


async def update_release(
    db: AsyncSession,
    project_id: UUID,
    release: Release,
    *,
    version: str | None = None,
    title: str | None = None,
    notes: str | None = None,
    qa_run_id: UUID | None = None,
    status: str | None = None,
    refresh_changelog: bool = False,
) -> Release:
    if version is not None:
        release.version = version.strip()[:64]
    if title is not None:
        release.title = title.strip()[:500]
    if notes is not None:
        release.notes = notes
    if qa_run_id is not None:
        await get_qa_run_or_404(db, project_id, qa_run_id)
        release.qa_run_id = qa_run_id
    if refresh_changelog:
        tasks = await list_tasks(db, project_id)
        release.changelog = build_changelog(tasks)

    if status is not None:
        mapped = _map_release_status(status)
        if mapped == ReleaseStatus.PUBLISHED and release.status != ReleaseStatus.PUBLISHED:
            release.status = ReleaseStatus.PUBLISHED
            release.published_at = datetime.now(timezone.utc)
        elif mapped == ReleaseStatus.DRAFT:
            release.status = ReleaseStatus.DRAFT
            release.published_at = None
        else:
            release.status = mapped

    await record_activity(
        db,
        project_id,
        summary=f"Updated release {release.version} ({release.status.value})",
        event_type="release.updated",
        actor=ActivityActor.USER,
        entity_type="release",
        entity_id=release.id,
    )
    await db.commit()
    await db.refresh(release)
    return release


async def delete_release(db: AsyncSession, project_id: UUID, release: Release) -> None:
    version = release.version
    release_id = release.id
    await db.delete(release)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted release {version}",
        event_type="release.deleted",
        actor=ActivityActor.USER,
        entity_type="release",
        entity_id=release_id,
    )
    await db.commit()


class ReleaseNotesLLMResult(BaseModel):
    notes: str = Field(description="Markdown release notes for humans")


async def generate_release_notes(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    release: Release,
) -> Release:
    await get_project_or_404(project_id, user_id, db)
    changelog = release.changelog or []
    lines = [
        f"- {entry.get('title')} ({entry.get('priority', 'unknown')})"
        for entry in changelog
        if isinstance(entry, dict)
    ] or ["No completed tasks yet."]

    prompt = PromptTemplate.from_template(
        """Write concise release notes for a solo-dev project.

Version: {version}
Title: {title}

Completed work:
{changelog}

Return practical release notes a human can publish. Use short sections if helpful.
"""
    )
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(ReleaseNotesLLMResult)

    try:
        result: ReleaseNotesLLMResult = await (prompt | model).ainvoke(
            {
                "version": release.version,
                "title": release.title,
                "changelog": "\n".join(lines),
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate release notes")

    release.notes = result.notes.strip()
    await record_activity(
        db,
        project_id,
        summary=f"Generated release notes for {release.version}",
        event_type="release.notes_generated",
        actor=ActivityActor.AI,
        entity_type="release",
        entity_id=release.id,
    )
    await db.commit()
    await db.refresh(release)
    return release


async def create_handoff(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    title: str,
    release_id: UUID | None = None,
    summary: str | None = None,
) -> Handoff:
    await get_project_or_404(project_id, user_id, db)
    release = None
    if release_id is not None:
        release = await get_release_or_404(db, project_id, release_id)

    payload = await build_handoff_payload(db, project_id, release)
    handoff = Handoff(
        project_id=project_id,
        release_id=release_id,
        title=title.strip()[:500],
        summary=summary,
        payload=payload,
        status=HandoffStatus.DRAFT,
    )
    db.add(handoff)
    await db.flush()
    await record_activity(
        db,
        project_id,
        summary=f"Created handoff draft “{handoff.title}”",
        event_type="handoff.created",
        actor=ActivityActor.USER,
        entity_type="handoff",
        entity_id=handoff.id,
    )
    await db.commit()
    await db.refresh(handoff)
    return handoff


async def update_handoff(
    db: AsyncSession,
    project_id: UUID,
    handoff: Handoff,
    *,
    title: str | None = None,
    summary: str | None = None,
    release_id: UUID | None = None,
    status: str | None = None,
    refresh_payload: bool = False,
) -> Handoff:
    if title is not None:
        handoff.title = title.strip()[:500]
    if summary is not None:
        handoff.summary = summary
    if release_id is not None:
        await get_release_or_404(db, project_id, release_id)
        handoff.release_id = release_id
    if refresh_payload or release_id is not None:
        release = None
        if handoff.release_id:
            release = await get_release_or_404(db, project_id, handoff.release_id)
        handoff.payload = await build_handoff_payload(db, project_id, release)

    if status is not None:
        mapped = _map_handoff_status(status)
        if mapped == HandoffStatus.FINAL and handoff.status != HandoffStatus.FINAL:
            handoff.status = HandoffStatus.FINAL
            handoff.finalized_at = datetime.now(timezone.utc)
            project = await db.get(Project, project_id)
            if project is not None:
                advance_to_handed_off(project)
        elif mapped == HandoffStatus.DRAFT:
            handoff.status = HandoffStatus.DRAFT
            handoff.finalized_at = None
        else:
            handoff.status = mapped

    await record_activity(
        db,
        project_id,
        summary=f"Updated handoff “{handoff.title}” ({handoff.status.value})",
        event_type="handoff.updated",
        actor=ActivityActor.USER,
        entity_type="handoff",
        entity_id=handoff.id,
    )
    await db.commit()
    await db.refresh(handoff)
    return handoff


async def delete_handoff(db: AsyncSession, project_id: UUID, handoff: Handoff) -> None:
    title = handoff.title
    handoff_id = handoff.id
    await db.delete(handoff)
    await record_activity(
        db,
        project_id,
        summary=f"Deleted handoff “{title}”",
        event_type="handoff.deleted",
        actor=ActivityActor.USER,
        entity_type="handoff",
        entity_id=handoff_id,
    )
    await db.commit()


class HandoffSummaryLLMResult(BaseModel):
    summary: str = Field(description="Markdown handoff summary for a client or teammate")


async def generate_handoff_summary(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    handoff: Handoff,
) -> Handoff:
    await get_project_or_404(project_id, user_id, db)
    release = None
    if handoff.release_id:
        release = await get_release_or_404(db, project_id, handoff.release_id)
    payload = await build_handoff_payload(db, project_id, release)
    handoff.payload = payload

    coverage = payload.get("coverage") or {}
    prompt = PromptTemplate.from_template(
        """Write a clear project handoff summary for a solo developer completing delivery.

Include: what shipped, QA posture, known risks/open questions, and how to continue.

Title: {title}
Release: {release}
Coverage: confirmed={confirmed}, done_tasks={done}/{total}, passed_qa={has_qa}
Open questions: {open_questions}
Blocked tasks: {blocked}
Decisions: {decisions}
Release notes:
{notes}
"""
    )
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(HandoffSummaryLLMResult)

    try:
        result: HandoffSummaryLLMResult = await (prompt | model).ainvoke(
            {
                "title": handoff.title,
                "release": (
                    f"{release.version} — {release.title}" if release else "None linked"
                ),
                "confirmed": coverage.get("confirmed_requirements", 0),
                "done": coverage.get("tasks_done", 0),
                "total": coverage.get("tasks_total", 0),
                "has_qa": coverage.get("has_passed_qa", False),
                "open_questions": "\n".join(
                    f"- {q['title']}" for q in payload.get("unresolved_open_questions", [])
                )
                or "None",
                "blocked": "\n".join(
                    f"- {t['title']}: {t.get('blocker_reason') or 'unspecified'}"
                    for t in payload.get("blocked_tasks", [])
                )
                or "None",
                "decisions": "\n".join(
                    f"- {d['title']}" for d in payload.get("active_decisions", [])
                )
                or "None",
                "notes": (release.notes if release and release.notes else "None"),
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="generate handoff summary")

    handoff.summary = result.summary.strip()
    await record_activity(
        db,
        project_id,
        summary=f"Generated handoff summary for “{handoff.title}”",
        event_type="handoff.summary_generated",
        actor=ActivityActor.AI,
        entity_type="handoff",
        entity_id=handoff.id,
    )
    await db.commit()
    await db.refresh(handoff)
    return handoff
