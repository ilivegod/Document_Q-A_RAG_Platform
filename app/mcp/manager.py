import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings
from app.mcp.schemas import WebFinding
from app.mcp.servers import McpServerConfig, get_ddg_server, get_wiki_server

logger = logging.getLogger(__name__)

_HTTP_USER_AGENT = "ProjectCopilot/1.0 (project document Q&A; +https://github.com/ilivegod/citadel)"


def _tool_result_to_text(result: Any) -> str:
    if result is None:
        return ""
    if hasattr(result, "content") and result.content:
        parts = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    if isinstance(result, str):
        return result
    return str(result)


class McpManager:
    """Spawn stdio MCP servers and call tools with timeout."""

    async def _with_session(
        self,
        config: McpServerConfig,
        callback,
    ):
        if not config.enabled:
            raise RuntimeError(f"MCP server {config.key} is disabled")

        params = StdioServerParameters(
            command=config.command,
            args=list(config.args),
        )
        async with asyncio.timeout(settings.mcp_tool_timeout_seconds):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await callback(session)

    async def list_tools(self, config: McpServerConfig) -> list[dict]:
        async def _list(session: ClientSession):
            response = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema,
                }
                for t in response.tools
            ]

        return await self._with_session(config, _list)

    async def call_tool(
        self,
        config: McpServerConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        async def _call(session: ClientSession):
            result = await session.call_tool(tool_name, arguments=arguments)
            return _tool_result_to_text(result)

        return await self._with_session(config, _call)

    async def search_duckduckgo(self, query: str, limit: int | None = None) -> str:
        limit = limit or settings.web_research_max_results
        try:
            config = get_ddg_server()
            tools = await self.list_tools(config)
            tool_name = _pick_tool(
                tools,
                preferred=[
                    "search",
                    "duckduckgo_web_search",
                    "web_search",
                ],
                contains=["search"],
            )
            args = _build_search_args(tool_name, query, limit)
            return await self.call_tool(config, tool_name, args)
        except Exception as e:
            logger.warning(
                "DuckDuckGo MCP unavailable (%s), using REST fallback",
                e,
            )
            return await _duckduckgo_rest_search(query, limit)

    async def search_wikipedia(self, query: str) -> str:
        try:
            config = get_wiki_server()
            tools = await self.list_tools(config)
            tool_name = _pick_tool(
                tools,
                preferred=[
                    "search_wikipedia",
                    "wikipedia_search",
                    "search",
                    "get_summary",
                ],
                contains=["search", "summary", "article"],
            )
            args = _build_wiki_args(tool_name, query)
            return await self.call_tool(config, tool_name, args)
        except Exception as e:
            logger.warning(
                "Wikipedia MCP unavailable (%s), using REST fallback",
                e,
            )
            return await _wikipedia_rest_search(query)


def _pick_tool(
    tools: list[dict],
    preferred: list[str],
    contains: list[str],
) -> str:
    names = [t["name"] for t in tools]
    for p in preferred:
        if p in names:
            return p
    for t in tools:
        name = t["name"].lower()
        if any(c in name for c in contains):
            return t["name"]
    if not names:
        raise RuntimeError("No MCP tools available on server")
    return names[0]


def _build_search_args(tool_name: str, query: str, limit: int) -> dict:
    name = tool_name.lower()
    if "duckduckgo_web_search" in name or "web_search" in name:
        return {"query": query[:400], "limit": limit}
    return {"query": query[:400], "max_results": limit}


def _build_wiki_args(tool_name: str, query: str) -> dict:
    name = tool_name.lower()
    if "summary" in name:
        return {"title": query, "query": query}
    return {"query": query, "q": query}


async def _wikipedia_rest_search(query: str) -> str:
    """Direct Wikipedia API when the stdio MCP server cannot start (e.g. Docker)."""
    limit = settings.web_research_max_results
    headers = {"User-Agent": _HTTP_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        search_resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": limit,
                "utf8": 1,
            },
        )
        search_resp.raise_for_status()
        searches = search_resp.json().get("query", {}).get("search", [])
        if not searches:
            return json.dumps([])

        titles = [item["title"] for item in searches]
        detail_resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts|info",
                "exintro": True,
                "explaintext": True,
                "titles": "|".join(titles),
                "format": "json",
                "inprop": "url",
            },
        )
        detail_resp.raise_for_status()
        pages = detail_resp.json().get("query", {}).get("pages", {})

    results: list[dict[str, str]] = []
    for item in searches:
        title = item["title"]
        page = pages.get(str(item.get("pageid", "")), {})
        if not page:
            for p in pages.values():
                if p.get("title") == title:
                    page = p
                    break
        snippet = (
            page.get("extract")
            or item.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")
        )
        url = page.get("fullurl") or f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        results.append({"title": title, "url": url, "snippet": snippet})

    return json.dumps(results[:limit])


def _flatten_ddg_topics(topics: list, out: list[dict], limit: int) -> None:
    for topic in topics:
        if len(out) >= limit:
            return
        if not isinstance(topic, dict):
            continue
        if "Topics" in topic:
            _flatten_ddg_topics(topic["Topics"], out, limit)
            continue
        text = topic.get("Text") or topic.get("Result")
        url = topic.get("FirstURL") or topic.get("FirstUrl") or ""
        if not text:
            continue
        title, _, body = text.partition(" - ")
        out.append(
            {
                "title": title or text[:120],
                "url": url,
                "snippet": body or text,
            }
        )


async def _duckduckgo_rest_search(query: str, limit: int) -> str:
    """Instant Answer API fallback when DuckDuckGo MCP is unavailable."""
    headers = {"User-Agent": _HTTP_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, str]] = []
    abstract = (data.get("AbstractText") or "").strip()
    abstract_url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or query).strip()
    if abstract:
        results.append(
            {
                "title": heading,
                "url": abstract_url,
                "snippet": abstract,
            }
        )

    _flatten_ddg_topics(data.get("RelatedTopics") or [], results, limit)
    return json.dumps(results[:limit])


def parse_web_findings(raw: str, provider: str) -> list[WebFinding]:
    """Best-effort parse of MCP tool output into structured findings."""
    if not raw or not raw.strip():
        return []

    findings: list[WebFinding] = []
    provider_lit = "wikipedia" if provider == "wikipedia" else "duckduckgo"

    try:
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("results", data.get("items", [data]))
        if isinstance(items, dict):
            items = [items]
        for item in items[: settings.web_research_max_results]:
            if not isinstance(item, dict):
                continue
            title = (
                item.get("title")
                or item.get("name")
                or item.get("heading")
                or "Web result"
            )
            url = item.get("url") or item.get("link") or item.get("href") or ""
            snippet = (
                item.get("snippet")
                or item.get("body")
                or item.get("extract")
                or item.get("summary")
                or item.get("description")
                or item.get("content")
                or str(item)[:500]
            )
            if url or snippet:
                findings.append(
                    WebFinding(
                        title=str(title)[:200],
                        url=str(url),
                        snippet=str(snippet)[:2000],
                        provider=provider_lit,
                    )
                )
        if findings:
            return findings
    except json.JSONDecodeError:
        pass

    url_pattern = re.compile(r"https?://[^\s\)\]\"']+")
    urls = url_pattern.findall(raw)
    if urls:
        for i, url in enumerate(urls[: settings.web_research_max_results]):
            findings.append(
                WebFinding(
                    title=f"{provider_lit.title()} result {i + 1}",
                    url=url.rstrip(".,)"),
                    snippet=raw[:1500],
                    provider=provider_lit,
                )
            )
        return findings

    findings.append(
        WebFinding(
            title=f"{provider_lit.title()} search",
            url="",
            snippet=raw[:2000],
            provider=provider_lit,
        )
    )
    return findings


mcp_manager = McpManager()
