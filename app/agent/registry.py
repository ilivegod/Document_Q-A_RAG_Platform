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
        return ALL_TOOLS
    if tier == UserTier.BUSINESS:
        return ALL_TOOLS
    if tier == UserTier.PRO:
        return TIER_GATED_PRO_TOOLS
    return TIER_GATED_FREE_TOOLS


def tier_allows_tool(tier: UserTier, tool_name: str) -> bool:
    return tool_name in tools_for_tier(tier)
