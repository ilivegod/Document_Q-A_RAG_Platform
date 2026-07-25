"""MCP client layer for external web search servers."""

from app.mcp.schemas import WebFinding
from app.mcp.manager import mcp_manager

__all__ = ["WebFinding", "mcp_manager"]
