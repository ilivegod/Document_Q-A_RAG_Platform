"""Tests for rule-based prospect fit scoring."""

from app.models.prospect import WebsiteStatus
from app.services.prospect_fit_heuristic import score_prospect_fit_heuristic


def test_no_website_high_score():
    fit = score_prospect_fit_heuristic(
        business_name="Joe's Dental",
        industry_keywords="dental clinic",
        website_status=WebsiteStatus.NONE,
        audit_signals={"signals": ["No website listed"]},
    )
    assert fit.fit_score >= 85
    assert "no website" in fit.fit_summary.lower()
    assert fit.pitch_angle == ""


def test_poor_website_moderate_high():
    fit = score_prospect_fit_heuristic(
        business_name="Old Shop",
        industry_keywords="retail",
        website_status=WebsiteStatus.POOR,
        audit_signals={
            "signals": ["No HTTPS", "Very thin homepage content", "Missing page title"],
            "https": False,
            "word_count": 40,
        },
    )
    assert 70 <= fit.fit_score <= 90


def test_ok_website_low_score():
    fit = score_prospect_fit_heuristic(
        business_name="Modern Co",
        industry_keywords="saas",
        website_status=WebsiteStatus.OK,
        audit_signals={"signals": [], "https": True, "word_count": 500},
    )
    assert fit.fit_score <= 30
