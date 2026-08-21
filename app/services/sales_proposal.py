"""Sales proposal lifecycle: draft from conversation + project context, revise, approve."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
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
from app.services.company_research import PROPOSAL_KINDS
from app.services.document_text import create_text_document_for_project
from app.services.project_access import get_project_or_404
from app.services.retrieval import similarity_search

logger = logging.getLogger(__name__)


def _append_progress(proposal: SalesProposal, message: str) -> None:
    log = list(proposal.progress_log or [])
    log.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "message": message,
        }
    )
    proposal.progress_log = log


class ProposalDraftResult(BaseModel):
    title: str
    markdown: str = Field(description="Full proposal body in markdown")


def infer_proposal_kind(user_intent: str | None) -> tuple[str, str]:
    """Heuristic proposal type from user instructions — no web research."""
    text = (user_intent or "").lower()
    if re.search(r"\b(seo|visibility|google maps|local search)\b", text):
        return "local_seo", PROPOSAL_KINDS["local_seo"]
    if re.search(r"\b(maintenance|retainer|support|care plan)\b", text):
        return "maintenance_retainer", PROPOSAL_KINDS["maintenance_retainer"]
    if re.search(r"\b(presence|social|brand)\b", text):
        return "digital_presence", PROPOSAL_KINDS["digital_presence"]
    if re.search(r"\b(website|redesign|site|web app|landing page)\b", text):
        return "website_redesign", PROPOSAL_KINDS["website_redesign"]
    return "general_pitch", PROPOSAL_KINDS["general_pitch"]


async def build_proposal_source_context(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    user_intent: str | None,
) -> dict:
    """Gather lead, project, user instructions, and optional project-doc RAG excerpts."""
    project = await get_project_or_404(project_id, user_id, db)
    prospect: Prospect | None = None
    if project.prospect_id:
        prospect = await db.get(Prospect, project.prospect_id)

    rag_excerpts: list[str] = []
    query = user_intent or project.description or project.name
    if query:
        try:
            chunks = await similarity_search(
                question=query[:500],
                db=db,
                user_id=user_id,
                project_id=project_id,
                k=6,
            )
            for chunk in chunks:
                rag_excerpts.append(chunk.content.strip()[:800])
        except Exception as exc:
            logger.warning("Proposal RAG lookup failed: %s", exc)

    return {
        "client_name": project.client_name or project.name,
        "project_description": project.description,
        "user_instructions": user_intent or "",
        "lead": {
            "business_name": prospect.business_name if prospect else None,
            "website_url": prospect.website_url if prospect else None,
            "website_status": prospect.website_status.value if prospect else None,
            "fit_summary": prospect.fit_summary if prospect else None,
            "pitch_angle": prospect.pitch_angle if prospect else None,
            "audit_signals": prospect.audit_signals if prospect else None,
        }
        if prospect
        else None,
        "project_document_excerpts": rag_excerpts,
        "source_note": (
            "Draft using ONLY user instructions, lead fields above, and document excerpts. "
            "Do not invent facts or use internet research."
        ),
    }


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
    """Start drafting a proposal from chat-approved user instructions (no web research)."""
    project = await get_project_or_404(project_id, user_id, db)

    existing = await get_active_proposal(db, project_id, user_id)
    if existing and existing.status in {
        SalesProposalStatus.RESEARCHING,
        SalesProposalStatus.DRAFTING,
    }:
        raise HTTPException(
            status_code=409,
            detail="A proposal draft is already in progress for this project.",
        )
    if existing and existing.status in {
        SalesProposalStatus.AWAITING_CONFIRMATION,
        SalesProposalStatus.DRAFT,
    }:
        raise HTTPException(
            status_code=409,
            detail="An active proposal already exists. Revise or approve it first.",
        )

    if not (user_intent or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Describe what to write in the conversation before approving the draft action.",
        )

    source_context = await build_proposal_source_context(
        db,
        project_id=project_id,
        user_id=user_id,
        user_intent=user_intent,
    )
    kind, kind_label = infer_proposal_kind(user_intent)

    proposal = SalesProposal(
        user_id=user_id,
        project_id=project_id,
        prospect_id=project.prospect_id,
        status=SalesProposalStatus.DRAFTING,
        user_intent=user_intent.strip(),
        research_summary=source_context,
        proposal_kind=kind,
        proposal_kind_label=kind_label,
        current_step="Drafting from your instructions",
        progress_log=[],
    )
    _append_progress(proposal, "Draft queued from your chat instructions")
    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    from app.workers.tasks import draft_sales_proposal_task

    draft_sales_proposal_task.delay(str(proposal.id))
    return proposal


async def run_proposal_research_job(proposal_id: UUID) -> None:
    """Legacy Celery entrypoint — forwards to draft job if still marked researching."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            proposal = await db.get(SalesProposal, proposal_id)
            if not proposal:
                return
            if proposal.status == SalesProposalStatus.RESEARCHING:
                proposal.status = SalesProposalStatus.DRAFTING
                proposal.current_step = "Drafting from your instructions"
                await db.commit()
    finally:
        await engine.dispose()
    from app.workers.tasks import draft_sales_proposal_task

    draft_sales_proposal_task.delay(str(proposal_id))


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

            research = proposal.research_summary or {}
            revision_feedback = ""
            if is_revision and proposal.revision_notes:
                last = proposal.revision_notes[-1]
                revision_feedback = last.get("feedback", "")

            prompt = PromptTemplate.from_template(
                """Write a concise, client-ready sales proposal in markdown for a boutique dev agency.

Client: {client_name}
Document type: {proposal_label}

PRIMARY SOURCE — what the user asked for (follow this closely):
{user_intent}

Supporting context (lead data, project notes, uploaded document excerpts — use only what is here):
{context_json}

{revision_block}

Rules:
- Do NOT add facts from the internet or guess details not in the sources above.
- If something is unknown, keep language general or omit it.
- When the user gave specific deliverables or scope, include them verbatim where appropriate.

Structure:
- Title (# heading)
- Executive summary
- Understanding of the client (from provided context only)
- Proposed approach
- Deliverables (bullet list)
- Timeline estimate (ranges)
- Next steps

Tone: professional and specific to the instructions. No placeholder brackets.
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
                        user_intent=proposal.user_intent or "",
                        context_json=str(research)[:8000],
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
