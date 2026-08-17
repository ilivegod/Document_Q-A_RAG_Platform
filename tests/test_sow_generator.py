"""Unit tests for SOW tier contingency and cost calculation."""
from decimal import Decimal

from app.models.requirement import Requirement, RequirementCategory, RequirementPriority, RequirementStatus
from app.services.sow_generator import (
    SowTierLLM,
    apply_contingency_to_tiers,
    build_tier_payloads_with_costs,
)


def _req(stable_id: str, category: RequirementCategory, priority: RequirementPriority):
    return Requirement(
        stable_id=stable_id,
        title=stable_id,
        category=category,
        priority=priority,
        status=RequirementStatus.CONFIRMED,
    )


def test_contingency_applied_for_ambiguous_requirement():
    requirements = [
        _req("REQ-001", RequirementCategory.FEATURE, RequirementPriority.MUST),
        _req("REQ-002", RequirementCategory.ASSUMPTION, RequirementPriority.UNKNOWN),
    ]
    tiers = [
        SowTierLLM(
            tier_key="mvp",
            tier_name="MVP",
            total_hours=100,
            requirement_ids=["REQ-001"],
        ),
        SowTierLLM(
            tier_key="recommended",
            tier_name="Recommended",
            total_hours=100,
            requirement_ids=["REQ-001", "REQ-002"],
        ),
    ]
    result = apply_contingency_to_tiers(tiers, requirements)
    assert result[0]["total_hours"] == 100.0
    assert result[0]["contingency_applied"] is False
    assert result[1]["total_hours"] == 115.0
    assert result[1]["contingency_applied"] is True


def test_tier_cost_from_hourly_rate():
    tier_dicts = [
        {
            "tier_key": "mvp",
            "tier_name": "MVP",
            "description": "",
            "total_hours": 120.0,
            "requirement_ids": ["REQ-001"],
            "estimated_weeks": 4,
            "contingency_applied": False,
        }
    ]
    priced = build_tier_payloads_with_costs(tier_dicts, Decimal("100.00"))
    assert priced[0]["total_cost"] == 12000.0
