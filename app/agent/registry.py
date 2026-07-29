from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from app.config import settings
from app.models.user import UserTier


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[str]]
    min_tier: UserTier = UserTier.FREE


# Tool names
SEARCH_DOCUMENTS = "search_documents"
KEYWORD_SEARCH = "keyword_search"
GET_PAGE_CONTENT = "get_page_content"
LIST_USER_DOCUMENTS = "list_user_documents"
WEB_RESEARCH = "web_research"

ALL_TOOLS = {
    SEARCH_DOCUMENTS,
    KEYWORD_SEARCH,
    GET_PAGE_CONTENT,
    LIST_USER_DOCUMENTS,
    WEB_RESEARCH,
}

TIER_GATED_FREE_TOOLS = {SEARCH_DOCUMENTS, LIST_USER_DOCUMENTS}
TIER_GATED_PRO_TOOLS = ALL_TOOLS


def tools_for_tier(tier: UserTier) -> set[str]:
    """Closed beta: full tool set for every approved user."""
    if settings.closed_beta_enabled:
        allowed = set(ALL_TOOLS)
    elif tier == UserTier.BUSINESS:
        allowed = set(ALL_TOOLS)
    elif tier == UserTier.PRO:
        allowed = set(TIER_GATED_PRO_TOOLS)
    else:
        allowed = set(TIER_GATED_FREE_TOOLS)

    # Web research is opt-in via MCP_WEB_ENABLED — never in the default loop.
    if not settings.mcp_web_enabled:
        allowed.discard(WEB_RESEARCH)
    return allowed


def tier_allows_tool(tier: UserTier, tool_name: str) -> bool:
    return tool_name in tools_for_tier(tier)
