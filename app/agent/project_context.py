"""Project-scoped context for agency project chat."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.prospect import Prospect
from app.services.sales_proposal import get_active_proposal


async def format_project_client_context(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
) -> str:
    """Lead, client, and active proposal state for the project agent."""
    project = await db.get(Project, project_id)
    if not project:
        return ""

    lines = [
        f"Client / project: {project.client_name or project.name}",
        f"Pipeline stage: {project.pipeline_stage.value}",
    ]
    if project.description:
        lines.append(f"Project notes: {project.description[:800]}")

    if project.prospect_id:
        prospect = await db.get(Prospect, project.prospect_id)
        if prospect:
            lines.extend([
                "",
                "Linked lead:",
                f"- Business: {prospect.business_name}",
                f"- Website: {prospect.website_url or 'none'} ({prospect.website_status.value})",
                f"- Fit score: {prospect.fit_score}",
                f"- Fit summary: {prospect.fit_summary or 'n/a'}",
                f"- Pitch angle: {prospect.pitch_angle or 'n/a'}",
                f"- Audit: {prospect.audit_signals or {}}",
            ])

    proposal = await get_active_proposal(db, project_id, user_id)
    if proposal:
        lines.extend([
            "",
            "Active document draft workflow:",
            f"- Status: {proposal.status.value}",
            f"- Type: {proposal.proposal_kind_label or proposal.proposal_kind or 'document'}",
            f"- Step: {proposal.current_step or 'in progress'}",
        ])
        if proposal.status.value in {"drafting", "draft", "awaiting_confirmation"}:
            lines.append(
                "- A draft is in progress or awaiting review. Do not suggest a new draft action."
            )
    else:
        lines.extend([
            "",
            "No active draft workflow. After the user explains what to write, "
            "suggest draft_proposal or draft_document with user_intent summarizing the chat.",
        ])

    return "\n".join(lines)
