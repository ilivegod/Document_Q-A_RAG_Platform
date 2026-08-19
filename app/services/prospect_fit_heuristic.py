"""Rule-based prospect fit scoring — no LLM (used during bulk discovery)."""

from __future__ import annotations

from app.models.prospect import WebsiteStatus
from app.services.prospect_fit import ProspectFitEvaluation


def score_prospect_fit_heuristic(
    *,
    business_name: str,
    industry_keywords: str,
    website_status: WebsiteStatus,
    audit_signals: dict | None,
) -> ProspectFitEvaluation:
    signals = (audit_signals or {}).get("signals") or []
    signal_count = len(signals)
    https = bool((audit_signals or {}).get("https"))
    word_count = int((audit_signals or {}).get("word_count") or 0)

    if website_status == WebsiteStatus.NONE:
        score = 88
        summary = (
            f"{business_name} has no website listed — strong candidate for a new site "
            f"and custom workflow tools in {industry_keywords}."
        )
    elif website_status == WebsiteStatus.POOR:
        if signal_count >= 3 or not https:
            score = 82
        elif signal_count >= 2:
            score = 74
        else:
            score = 66
        signal_hint = ", ".join(signals[:4]) if signals else "quality issues detected"
        summary = (
            f"{business_name} has a weak web presence ({signal_hint}). "
            f"Good fit for a rebuild or digitization pitch."
        )
    elif website_status == WebsiteStatus.OK:
        if signal_count >= 2:
            score = 38
            summary = (
                f"{business_name} has a functional site with some issues — "
                f"may still need custom tools beyond the marketing site."
            )
        else:
            score = 22
            summary = (
                f"{business_name} already has a solid website ({word_count} words on homepage). "
                f"Lower priority unless they need bespoke software."
            )
    else:
        score = 45
        summary = (
            f"{business_name} — website quality unclear. Review manually for "
            f"{industry_keywords} opportunities."
        )

    score = max(0, min(100, score))

    return ProspectFitEvaluation(
        fit_score=score,
        fit_summary=summary,
        pitch_angle="",
    )
