"""Company research for sales proposals: prospect context + web search."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.web_agent import run_web_agent
from app.config import settings
from app.models.prospect import Prospect
from app.services.llm_errors import raise_llm_http_error

logger = logging.getLogger(__name__)

PROPOSAL_KINDS = {
    "website_redesign": "Website redesign",
    "local_seo": "Local SEO & visibility",
    "general_pitch": "General digital partnership",
    "digital_presence": "Online presence upgrade",
    "maintenance_retainer": "Website care & maintenance",
}


class CompanyResearchBrief(BaseModel):
    company_overview: str = Field(description="2-4 sentence overview of the business")
    key_observations: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    suggested_proposal_kind: str = Field(
        description="One of: website_redesign, local_seo, general_pitch, digital_presence, maintenance_retainer"
    )
    suggested_proposal_label: str = Field(
        description="Human-readable name for the suggested proposal type"
    )
    rationale: str = Field(description="One sentence why this proposal type fits")
    confirmation_question: str = Field(
        description="Short question asking the user to confirm or adjust the approach"
    )
    web_sources: list[str] = Field(default_factory=list)


def _format_prospect_context(prospect: Prospect | None, project_name: str) -> str:
    if not prospect:
        return f"Project/client name: {project_name}\nNo linked prospect record."
    parts = [
        f"Business: {prospect.business_name}",
        f"Website: {prospect.website_url or 'none'}",
        f"Address: {prospect.address or 'unknown'}",
        f"Fit score: {prospect.fit_score}",
        f"Fit summary: {prospect.fit_summary or ''}",
        f"Pitch angle: {prospect.pitch_angle or ''}",
        f"Audit signals: {prospect.audit_signals or {}}",
    ]
    return "\n".join(parts)


async def run_company_research(
    db: AsyncSession,
    *,
    prospect_id: UUID | None,
    project_name: str,
    user_intent: str | None = None,
) -> dict[str, Any]:
    """Gather prospect + web context and produce structured research brief."""
    prospect: Prospect | None = None
    if prospect_id:
        prospect = await db.get(Prospect, prospect_id)

    context = _format_prospect_context(prospect, project_name)
    search_query = user_intent or f"{project_name} business website services"
    if prospect and prospect.website_url:
        search_query = f"{prospect.business_name} {prospect.website_url} reviews services"

    web_summary, findings, _sub_steps = await run_web_agent(
        query=search_query,
        prefer="duckduckgo",
    )
    web_sources = [f.url for f in findings if f.url][:8]

    prompt = PromptTemplate.from_template(
        """You are a boutique agency strategist researching a local business lead.

Prospect / project context:
{context}

User intent (if any): {user_intent}

Web research summary:
{web_summary}

Web source URLs:
{web_sources}

Based on audit signals, fit summary, and web research, produce a structured company brief
and suggest ONE proposal type the agency should pitch.

Valid proposal kinds: website_redesign, local_seo, general_pitch, digital_presence, maintenance_retainer.
Prefer website_redesign when the site is missing or poor. Prefer local_seo when the site exists but visibility is weak.
"""
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    )
    structured = llm.with_structured_output(CompanyResearchBrief)

    try:
        brief: CompanyResearchBrief = await structured.ainvoke(
            prompt.format(
                context=context,
                user_intent=user_intent or "Research company and suggest best proposal approach",
                web_summary=web_summary[:6000],
                web_sources="\n".join(web_sources) or "none",
            )
        )
    except Exception as exc:
        logger.exception("Company research LLM failed")
        raise_llm_http_error(exc)

    kind = brief.suggested_proposal_kind
    if kind not in PROPOSAL_KINDS:
        kind = "general_pitch"
        brief.suggested_proposal_label = PROPOSAL_KINDS[kind]

    research_summary = {
        "company_overview": brief.company_overview,
        "key_observations": brief.key_observations,
        "opportunities": brief.opportunities,
        "web_sources": web_sources or brief.web_sources,
        "web_research_excerpt": web_summary[:2000],
    }

    return {
        "research_summary": research_summary,
        "proposal_kind": kind,
        "proposal_kind_label": brief.suggested_proposal_label or PROPOSAL_KINDS.get(kind, kind),
        "confirmation_question": brief.confirmation_question,
        "rationale": brief.rationale,
    }
