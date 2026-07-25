import json

import pytest

from app.agent.web_agent import format_findings_for_tool_message, run_web_agent
from app.mcp.manager import parse_web_findings
from app.mcp.schemas import WebFinding


def test_parse_web_findings_json():
    raw = json.dumps(
        [
            {
                "title": "Test Article",
                "url": "https://example.com/a",
                "snippet": "Summary text",
            }
        ]
    )
    findings = parse_web_findings(raw, "wikipedia")
    assert len(findings) == 1
    assert findings[0].title == "Test Article"
    assert findings[0].provider == "wikipedia"


def test_format_findings_for_tool_message():
    findings = [
        WebFinding(
            title="A",
            url="https://a.test",
            snippet="Snippet A",
            provider="duckduckgo",
        )
    ]
    text = format_findings_for_tool_message(findings)
    assert "[W1]" in text
    assert "duckduckgo" in text


@pytest.mark.asyncio
async def test_run_web_agent_disabled(monkeypatch):
    monkeypatch.setattr("app.agent.web_agent.settings.mcp_web_enabled", False)
    summary, findings, sub_steps = await run_web_agent("test query")
    assert "disabled" in summary.lower()
    assert findings == []
    assert sub_steps == []


@pytest.mark.asyncio
async def test_run_web_agent_mocked_mcp(monkeypatch):
    monkeypatch.setattr("app.agent.web_agent.settings.mcp_web_enabled", True)
    monkeypatch.setattr("app.agent.web_agent.settings.google_api_key", "test-key")

    async def fake_wiki(query: str) -> str:
        return json.dumps(
            [{"title": "Wiki Page", "url": "https://wiki.test", "snippet": "From wiki"}]
        )

    async def fake_ddg(query: str) -> str:
        return json.dumps(
            [{"title": "DDG Page", "url": "https://ddg.test", "snippet": "From ddg"}]
        )

    async def fake_build_tools(findings, sub_steps):
        async def _wiki_search(query: str) -> str:
            raw = await fake_wiki(query)
            findings.extend(parse_web_findings(raw, "wikipedia"))
            sub_steps.append({"tool": "wikipedia_search", "provider": "wikipedia"})
            return raw

        async def _ddg_search(query: str) -> str:
            raw = await fake_ddg(query)
            findings.extend(parse_web_findings(raw, "duckduckgo"))
            sub_steps.append({"tool": "duckduckgo_search", "provider": "duckduckgo"})
            return raw

        from langchain_core.tools import StructuredTool

        tools = [
            StructuredTool.from_function(
                coroutine=_wiki_search,
                name="wikipedia_search",
                description="wiki",
            ),
            StructuredTool.from_function(
                coroutine=_ddg_search,
                name="duckduckgo_search",
                description="ddg",
            ),
        ]
        return tools, {
            "wikipedia_search": _wiki_search,
            "duckduckgo_search": _ddg_search,
        }

    monkeypatch.setattr("app.agent.web_agent._build_mcp_tools", fake_build_tools)

    class FakeResponse:
        def __init__(self, content="", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []

    calls = {"n": 0}

    class FakeModel:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResponse(
                    tool_calls=[
                        {"name": "wikipedia_search", "args": {"query": "test"}, "id": "1"}
                    ]
                )
            return FakeResponse(content="Summary from wiki")

    monkeypatch.setattr(
        "app.agent.web_agent.ChatGoogleGenerativeAI",
        lambda **kwargs: FakeModel(),
    )

    summary, findings, sub_steps = await run_web_agent("test query", prefer="wikipedia")
    assert len(findings) >= 1
    assert findings[0].provider == "wikipedia"
    assert sub_steps
