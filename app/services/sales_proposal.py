"""Sales proposal lifecycle: research, confirm, draft, revise, approve."""

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.project import Project
from app.models.prospect import Prospect
from app.models.sales_proposal import SalesProposal, SalesProposalStatus
from app.services.company_research import PROPOSAL_KINDS, run_company_research
from app.services.document_text import create_text_document_for_project
from app.services.llm_errors import raise_llm_http_error
from app.services.project_access import get_project_or_404

logger = logging.getLogger(__name__)


class ProposalDraftResult(BaseModel):
    title: str
    markdown: str = Field(description="Full proposal body in markdown")


def _append_progress(proposal: SalesProposal, message: str) -> None:
    log = list(proposal.progress_log or [])
    log.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }
    )
    proposal.progress_log = log


async def get_active_proposal(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> SalesProposal | None:
    await get_project_or_404(project_id, user_id, db)
    result = await db.execute(
        select(SalesProposal)
        .where(
            SalesProposal.project_id == project_id,
            SalesProposal.user_id == user_id,
            SalesProposal.status != SalesProposalStatus.APPROVED,
        )
        .order_by(SalesProposal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def start_proposal_research(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    user_intent: str | None = None,
) -> SalesProposal:
    project = await get_project_or_404(project_id, user_id, db)

    existing = await get_active_proposal(db, project_id, user_id)
    if existing and existing.status in {
        SalesProposalStatus.RESEARCHING,
        SalesProposalStatus.DRAFTING,
    }:
        raise HTTPException(
            status_code=409,
            detail="A proposal research job is already in progress for this project.",
        )
    if existing and existing.status in {
        SalesProposalStatus.AWAITING_CONFIRMATION,
        SalesProposalStatus.DRAFT,
    }:
        raise HTTPException(
            status_code=409,
            detail="An active proposal already exists. Confirm, revise, or approve it first.",
        )

    proposal = SalesProposal(
        user_id=user_id,
        project_id=project_id,
        prospect_id=project.prospect_id,
        status=SalesProposalStatus.RESEARCHING,
        user_intent=user_intent,
        current_step="Queued for research",
        progress_log=[],
    )
    _append_progress(proposal, "Research job queued")
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def run_proposal_research_job(proposal_id: UUID) -> None:
    """Celery worker: web + LLM research → awaiting_confirmation."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            proposal = await db.get(SalesProposal, proposal_id)
            if not proposal:
                logger.error("Sales proposal %s not found", proposal_id)
                return
            if proposal.status != SalesProposalStatus.RESEARCHING:
                return

            project = await db.get(Project, proposal.project_id)
            if not project:
                proposal.status = SalesProposalStatus.FAILED
                proposal.error_message = "Project not found"
                await db.commit()
                return

            proposal.current_step = "Researching company and web presence"
            _append_progress(proposal, proposal.current_step)
            await db.commit()

            try:
                result = await run_company_research(
                    db,
                    prospect_id=proposal.prospect_id or project.prospect_id,
                    project_name=project.client_name or project.name,
                    user_intent=proposal.user_intent,
                )
            except Exception as exc:
                logger.exception("Proposal research failed for %s", proposal_id)
                proposal.status = SalesProposalStatus.FAILED
                proposal.error_message = str(exc)[:500]
                proposal.current_step = "Research failed"
                _append_progress(proposal, f"Failed: {proposal.error_message}")
                await db.commit()
                return

            proposal.research_summary = result["research_summary"]
            proposal.proposal_kind = result["proposal_kind"]
            proposal.proposal_kind_label = result["proposal_kind_label"]
            proposal.confirmation_question = result["confirmation_question"]
            proposal.status = SalesProposalStatus.AWAITING_CONFIRMATION
            proposal.current_step = "Awaiting your confirmation on proposal approach"
            _append_progress(
                proposal,
                f"Suggested: {proposal.proposal_kind_label} — {result.get('rationale', '')}",
            )
            await db.commit()
    finally:
        await engine.dispose()


async def confirm_proposal_type(
    db: AsyncSession,
    *,
    project_id: UUID,
    proposal_id: UUID,
    user_id: UUID,
    proposal_kind: str | None = None,
    custom_approach: str | None = None,
) -> SalesProposal:
    proposal = await _get_proposal_for_user(db, project_id, proposal_id, user_id)
    if proposal.status != SalesProposalStatus.AWAITING_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Proposal is not awaiting confirmation.")

    if proposal_kind:
        if proposal_kind not in PROPOSAL_KINDS:
            raise HTTPException(status_code=400, detail="Invalid proposal kind.")
        proposal.proposal_kind = proposal_kind
        proposal.proposal_kind_label = PROPOSAL_KINDS[proposal_kind]
    if custom_approach:
        proposal.user_intent = custom_approach

    proposal.status = SalesProposalStatus.DRAFTING
    proposal.current_step = "Generating draft proposal"
    _append_progress(proposal, "Confirmed approach — drafting proposal")
    await db.commit()
    await db.refresh(proposal)

    from app.workers.tasks import draft_sales_proposal_task

    draft_sales_proposal_task.delay(str(proposal.id))
    return proposal


async def run_proposal_draft_job(proposal_id: UUID, *, is_revision: bool = False) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            proposal = await db.get(SalesProposal, proposal_id)
            if not proposal:
                return
            if proposal.status != SalesProposalStatus.DRAFTING:
                return

            project = await db.get(Project, proposal.project_id)
            prospect = None
            if proposal.prospect_id:
                prospect = await db.get(Prospect, proposal.prospect_id)

            research = proposal.research_summary or {}
            revision_feedback = ""
            if is_revision and proposal.revision_notes:
                last = proposal.revision_notes[-1]
                revision_feedback = last.get("feedback", "")

            prompt = PromptTemplate.from_template(
                """Write a concise, client-ready sales proposal in markdown for a boutique dev agency.

Client: {client_name}
Proposal type: {proposal_label} ({proposal_kind})
User intent: {user_intent}

Company research:
{research_json}

{revision_block}

Structure:
- Title (# heading)
- Executive summary
- What we observed about their business
- Proposed approach (scoped to the proposal type)
- Deliverables (bullet list)
- Timeline estimate (ranges, not fixed dates)
- Next steps

Tone: professional, specific to this business, not generic boilerplate. No placeholder brackets.
"""
            )

            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key=settings.google_api_key,
            )
            structured = llm.with_structured_output(ProposalDraftResult)

            try:
                draft: ProposalDraftResult = await structured.ainvoke(
                    prompt.format(
                        client_name=project.client_name or project.name if project else "Client",
                        proposal_label=proposal.proposal_kind_label or "Proposal",
                        proposal_kind=proposal.proposal_kind or "general_pitch",
                        user_intent=proposal.user_intent or "",
                        research_json=str(research)[:8000],
                        revision_block=(
                            f"Apply this revision feedback:\n{revision_feedback}"
                            if revision_feedback
                            else ""
                        ),
                    )
                )
            except Exception as exc:
                logger.exception("Proposal draft LLM failed")
                proposal.status = SalesProposalStatus.FAILED
                proposal.error_message = str(exc)[:500]
                await db.commit()
                return

            body = draft.markdown.strip()
            if draft.title and not body.startswith("#"):
                body = f"# {draft.title}\n\n{body}"

            proposal.content_markdown = body
            proposal.status = SalesProposalStatus.DRAFT
            proposal.current_step = "Draft ready for review"
            if is_revision:
                proposal.revision_count = (proposal.revision_count or 0) + 1
            _append_progress(proposal, "Draft ready for your review")
            await db.commit()
    finally:
        await engine.dispose()


async def revise_proposal(
    db: AsyncSession,
    *,
    project_id: UUID,
    proposal_id: UUID,
    user_id: UUID,
    feedback: str,
) -> SalesProposal:
    proposal = await _get_proposal_for_user(db, project_id, proposal_id, user_id)
    if proposal.status != SalesProposalStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft proposals can be revised.")

    feedback = feedback.strip()
    if not feedback:
        raise HTTPException(status_code=400, detail="Feedback is required.")

    notes = list(proposal.revision_notes or [])
    notes.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "feedback": feedback,
        }
    )
    proposal.revision_notes = notes
    proposal.status = SalesProposalStatus.DRAFTING
    proposal.current_step = "Applying your feedback"
    _append_progress(proposal, f"Revision requested: {feedback[:120]}")
    await db.commit()
    await db.refresh(proposal)

    from app.workers.tasks import draft_sales_proposal_task

    draft_sales_proposal_task.delay(str(proposal.id), is_revision=True)
    return proposal


async def approve_proposal(
    db: AsyncSession,
    *,
    project_id: UUID,
    proposal_id: UUID,
    user_id: UUID,
) -> SalesProposal:
    proposal = await _get_proposal_for_user(db, project_id, proposal_id, user_id)
    if proposal.status != SalesProposalStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft proposals can be approved.")
    if not proposal.content_markdown:
        raise HTTPException(status_code=400, detail="Proposal has no content.")

    project = await get_project_or_404(project_id, user_id, db)
    client = (project.client_name or project.name or "Client").replace("/", "-")[:60]
    version = (proposal.revision_count or 0) + 1
    file_name = f"{client} - Proposal v{version}.md"

    doc = await create_text_document_for_project(
        db,
        user_id=user_id,
        project_id=project_id,
        file_name=file_name,
        content=proposal.content_markdown,
    )

    proposal.document_id = doc.id
    proposal.status = SalesProposalStatus.APPROVED
    proposal.completed_at = datetime.now(timezone.utc)
    proposal.current_step = "Approved — saved to Documents"
    _append_progress(proposal, f"Approved and saved as {file_name}")
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def _get_proposal_for_user(
    db: AsyncSession,
    project_id: UUID,
    proposal_id: UUID,
    user_id: UUID,
) -> SalesProposal:
    await get_project_or_404(project_id, user_id, db)
    proposal = await db.get(SalesProposal, proposal_id)
    if not proposal or proposal.project_id != project_id or proposal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposal
