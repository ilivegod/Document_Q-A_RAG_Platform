"""Seed a Company Brief document when converting a prospect to a project."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prospect import Prospect
from app.services.document_text import create_text_document_for_project


def build_company_brief_markdown(prospect: Prospect) -> str:
    lines = [
        f"# Company Brief: {prospect.business_name}",
        "",
        "## Overview",
        prospect.fit_summary or "No fit summary available yet.",
        "",
    ]
    if prospect.website_url:
        lines.extend(["## Website", prospect.website_url, ""])
    if prospect.address:
        lines.extend(["## Location", prospect.address, ""])
    if prospect.phone:
        lines.extend(["## Phone", prospect.phone, ""])
    if prospect.pitch_angle:
        lines.extend(["## Pitch angle", prospect.pitch_angle, ""])
    if prospect.audit_signals:
        lines.extend(["## Website audit signals", ""])
        if isinstance(prospect.audit_signals, dict):
            for key, value in prospect.audit_signals.items():
                lines.append(f"- **{key}**: {value}")
        else:
            lines.append(str(prospect.audit_signals))
        lines.append("")
    if prospect.fit_score is not None:
        lines.extend(["## Fit score", f"{prospect.fit_score}/100", ""])
    lines.extend([
        "---",
        "_Auto-generated from lead research when the project was created._",
    ])
    return "\n".join(lines)


async def seed_company_brief_document(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    prospect: Prospect,
) -> UUID:
    content = build_company_brief_markdown(prospect)
    safe_name = prospect.business_name.replace("/", "-")[:80]
    doc = await create_text_document_for_project(
        db,
        user_id=user_id,
        project_id=project_id,
        file_name=f"{safe_name} - Company Brief.md",
        content=content,
    )
    return doc.id
