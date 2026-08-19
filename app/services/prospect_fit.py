"""LLM fit scoring for prospect outreach."""

from __future__ import annotations

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.config import settings
from app.models.prospect import WebsiteStatus
from app.services.llm_errors import raise_llm_http_error


class ProspectFitEvaluation(BaseModel):
    fit_score: int = Field(ge=0, le=100, description="Custom software / digital upgrade fit")
    fit_summary: str = Field(description="Why this business is or isn't a good prospect")
    pitch_angle: str = Field(description="1-2 sentence outreach hook")


async def score_prospect_fit(
    *,
    business_name: str,
    industry_keywords: str,
    website_status: WebsiteStatus,
    audit_signals: dict | None,
    homepage_text: str,
    niche_notes: str | None = None,
) -> ProspectFitEvaluation:
    signals = audit_signals or {}
    signal_lines = signals.get("signals") or []
    prompt = PromptTemplate.from_template(
        """You are a boutique dev agency partner scoring outbound leads.

Business: {business_name}
Industry search: {industry_keywords}
Website status: {website_status}
Audit signals: {signal_lines}
Homepage excerpt: {homepage_text}
Agency niche notes: {niche_notes}

Score fit for pitching custom software, web app rebuilds, or workflow digitization.
High fit: outdated/no website, operational businesses that need bespoke tools.
Low fit: already modern product company, franchise with locked stack, irrelevant category.

Return fit_score 0-100, fit_summary, and pitch_angle for a short cold email opener."""
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    ).with_structured_output(ProspectFitEvaluation)

    try:
        return await (prompt | model).ainvoke(
            {
                "business_name": business_name,
                "industry_keywords": industry_keywords,
                "website_status": website_status.value,
                "signal_lines": ", ".join(signal_lines) or "none",
                "homepage_text": (homepage_text or "No content")[:2000],
                "niche_notes": niche_notes or "General agency outreach",
            }
        )
    except Exception as e:
        raise_llm_http_error(e, action="score prospect fit")
