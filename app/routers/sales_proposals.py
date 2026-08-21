from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User
from app.schemas.sales_proposal import (
    SalesProposalConfirmRequest,
    SalesProposalResearchRequest,
    SalesProposalResponse,
    SalesProposalReviseRequest,
)
from app.services.sales_proposal import (
    approve_proposal,
    confirm_proposal_type,
    get_active_proposal,
    revise_proposal,
    start_proposal_research,
)
from app.workers.tasks import research_sales_proposal_task

router = APIRouter(prefix="/projects", tags=["sales-proposals"])


def _to_response(proposal) -> SalesProposalResponse:
    return SalesProposalResponse(
        id=proposal.id,
        project_id=proposal.project_id,
        prospect_id=proposal.prospect_id,
        status=proposal.status.value,
        proposal_kind=proposal.proposal_kind,
        proposal_kind_label=proposal.proposal_kind_label,
        user_intent=proposal.user_intent,
        research_summary=proposal.research_summary,
        confirmation_question=proposal.confirmation_question,
        content_markdown=proposal.content_markdown,
        revision_count=proposal.revision_count or 0,
        revision_notes=list(proposal.revision_notes or []),
        document_id=proposal.document_id,
        error_message=proposal.error_message,
        current_step=proposal.current_step,
        progress_log=list(proposal.progress_log or []),
        created_at=proposal.created_at,
        completed_at=proposal.completed_at,
    )


@router.post("/{project_id}/proposals/research", response_model=SalesProposalResponse)
async def research_proposal(
    project_id: UUID,
    body: SalesProposalResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = await start_proposal_research(
        db,
        project_id=project_id,
        user_id=current_user.id,
        user_intent=body.user_intent,
    )
    research_sales_proposal_task.delay(str(proposal.id))
    return _to_response(proposal)


@router.get("/{project_id}/proposals/active", response_model=SalesProposalResponse | None)
async def get_active_proposal_route(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = await get_active_proposal(db, project_id, current_user.id)
    if not proposal:
        return None
    return _to_response(proposal)


@router.post(
    "/{project_id}/proposals/{proposal_id}/confirm-type",
    response_model=SalesProposalResponse,
)
async def confirm_proposal_type_route(
    project_id: UUID,
    proposal_id: UUID,
    body: SalesProposalConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = await confirm_proposal_type(
        db,
        project_id=project_id,
        proposal_id=proposal_id,
        user_id=current_user.id,
        proposal_kind=body.proposal_kind,
        custom_approach=body.custom_approach,
    )
    return _to_response(proposal)


@router.post(
    "/{project_id}/proposals/{proposal_id}/revise",
    response_model=SalesProposalResponse,
)
async def revise_proposal_route(
    project_id: UUID,
    proposal_id: UUID,
    body: SalesProposalReviseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = await revise_proposal(
        db,
        project_id=project_id,
        proposal_id=proposal_id,
        user_id=current_user.id,
        feedback=body.feedback,
    )
    return _to_response(proposal)


@router.post(
    "/{project_id}/proposals/{proposal_id}/approve",
    response_model=SalesProposalResponse,
)
async def approve_proposal_route(
    project_id: UUID,
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proposal = await approve_proposal(
        db,
        project_id=project_id,
        proposal_id=proposal_id,
        user_id=current_user.id,
    )
    return _to_response(proposal)
