import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.mcp.manager import mcp_manager, parse_web_findings
from app.mcp.schemas import WebFinding

logger = logging.getLogger(__name__)

MAX_WEB_TOOL_CALLS = 3

WEB_AGENT_SYSTEM = """You are a focused web research assistant supporting DocQA document Q&A.

Rules:
- You only search for facts that help explain something referenced in the user's uploaded documents.
- Prefer Wikipedia for definitions, entities, and encyclopedic topics.
- Prefer DuckDuckGo for niche technical references when Wikipedia is insufficient.
- Call at most 3 search tools total, then stop and summarize findings.
- Never invent URLs or facts not returned by tools.
- Do not search for weather, news, sports, or general off-topic queries.
"""


def format_findings_for_tool_message(findings: list[WebFinding]) -> str:
    if not findings:
        return "No web results found."
    lines = []
    for i, finding in enumerate(findings, 1):
        lines.append(
            f"[W{i}] {finding.title} ({finding.provider}): {finding.snippet[:400]}"
        )
        if finding.url:
            lines.append(f"  URL: {finding.url}")
    return "\n".join(lines)


async def _build_mcp_tools(
    findings: list[WebFinding],
    sub_steps: list[dict],
) -> tuple[list[StructuredTool], dict]:
    tools: list[StructuredTool] = []

    async def _wiki_search(query: str) -> str:
        try:
            raw = await mcp_manager.search_wikipedia(query[:400])
            provider = "wikipedia"
        except Exception as e:
            logger.warning("Wikipedia search failed, trying DuckDuckGo: %s", e)
            raw = await mcp_manager.search_duckduckgo(query[:400])
            provider = "duckduckgo"
            sub_steps.append(
                {"tool": "duckduckgo_search", "provider": "duckduckgo", "fallback": True}
            )
            parsed = parse_web_findings(raw, provider)
            findings.extend(parsed)
            return raw

        parsed = parse_web_findings(raw, provider)
        findings.extend(parsed)
        sub_steps.append({"tool": "wikipedia_search", "provider": "wikipedia"})
        return raw

    async def _ddg_search(query: str) -> str:
        raw = await mcp_manager.search_duckduckgo(query[:400])
        parsed = parse_web_findings(raw, "duckduckgo")
        findings.extend(parsed)
        sub_steps.append({"tool": "duckduckgo_search", "provider": "duckduckgo"})
        return raw

    tools.append(
        StructuredTool.from_function(
            coroutine=_wiki_search,
            name="wikipedia_search",
            description="Search Wikipedia for encyclopedic facts, definitions, and entities.",
        )
    )
    tools.append(
        StructuredTool.from_function(
            coroutine=_ddg_search,
            name="duckduckgo_search",
            description="Search the web via DuckDuckGo for current events and general web pages.",
        )
    )
    return tools, {"wikipedia_search": _wiki_search, "duckduckgo_search": _ddg_search}


async def run_web_agent(
    query: str,
    prefer: str = "auto",
) -> tuple[str, list[WebFinding], list[dict]]:
    """Run the web sub-agent. Returns summary text, findings, and sub-agent trace."""
    if not settings.mcp_web_enabled:
        return (
            "Web search is disabled (MCP_WEB_ENABLED=false).",
            [],
            [],
        )

    prefer = (prefer or "auto").lower()
    if prefer not in {"auto", "wikipedia", "duckduckgo"}:
        prefer = "auto"

    findings: list[WebFinding] = []
    sub_steps: list[dict] = []

    try:
        tools, tool_fns = await _build_mcp_tools(findings, sub_steps)
    except Exception as e:
        logger.error("Failed to initialize MCP tools: %s", e, exc_info=True)
        return (f"Web search unavailable: {e}", [], [])

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.google_api_key,
    )
    model_with_tools = model.bind_tools(tools)

    prefer_hint = {
        "auto": "Choose the best provider automatically.",
        "wikipedia": "Start with wikipedia_search.",
        "duckduckgo": "Start with duckduckgo_search.",
    }[prefer]

    messages: list[Any] = [
        SystemMessage(content=WEB_AGENT_SYSTEM),
        HumanMessage(content=f"Research query: {query}\nPreference: {prefer_hint}"),
    ]

    tool_call_count = 0
    summary = ""

    while tool_call_count < MAX_WEB_TOOL_CALLS:
        try:
            response = await model_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error("Web agent LLM error: %s", e, exc_info=True)
            if findings:
                break
            return (f"Web search failed: {e}", findings, sub_steps)

        messages.append(response)

        if not getattr(response, "tool_calls", None):
            summary = response.content or ""
            break

        for tc in response.tool_calls:
            tool_call_count += 1
            name = tc["name"]
            args = tc.get("args") or {}
            query_arg = args.get("query") or query
            try:
                fn = tool_fns.get(name)
                if fn:
                    result = await fn(query=query_arg)
                else:
                    result = f"Unknown tool: {name}"
            except Exception as e:
                logger.error("Web MCP tool %s failed: %s", name, e, exc_info=True)
                result = f"Tool error: {e}"

            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
            if tool_call_count >= MAX_WEB_TOOL_CALLS:
                break

    if not summary:
        if findings:
            summary = format_findings_for_tool_message(findings)
        else:
            summary = "No relevant web results found."

    deduped: list[WebFinding] = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.url or f.title, f.provider)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    return summary, deduped[: settings.web_research_max_results], sub_steps
