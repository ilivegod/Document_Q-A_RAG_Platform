from app.agent.registry import tools_for_tier, tier_allows_tool, ALL_TOOLS
from app.agent.tools.handlers import build_tool_specs
from app.models.user import UserTier


def test_closed_beta_unlocks_all_tools_for_free_tier(monkeypatch):
    monkeypatch.setattr("app.agent.registry.settings.closed_beta_enabled", True)
    tools = tools_for_tier(UserTier.FREE)
    assert tools == ALL_TOOLS
    assert tier_allows_tool(UserTier.FREE, "keyword_search")
    assert tier_allows_tool(UserTier.FREE, "web_research")
    specs = build_tool_specs(UserTier.FREE)
    assert len(specs) >= 5


def test_tier_gating_when_closed_beta_disabled(monkeypatch):
    monkeypatch.setattr("app.agent.registry.settings.closed_beta_enabled", False)
    tools = tools_for_tier(UserTier.FREE)
    assert "search_documents" in tools
    assert "keyword_search" not in tools
    assert tier_allows_tool(UserTier.PRO, "keyword_search")
