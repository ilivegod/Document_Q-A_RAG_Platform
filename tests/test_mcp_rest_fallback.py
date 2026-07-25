import json
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.manager import (
    _duckduckgo_rest_search,
    _wikipedia_rest_search,
    parse_web_findings,
)


@pytest.mark.asyncio
async def test_wikipedia_rest_search_parses_results():
    search_payload = {
        "query": {
            "search": [
                {"pageid": 1, "title": "Critical thinking", "snippet": "match"},
            ]
        }
    }
    detail_payload = {
        "query": {
            "pages": {
                "1": {
                    "title": "Critical thinking",
                    "extract": "Critical thinking is disciplined thinking.",
                    "fullurl": "https://en.wikipedia.org/wiki/Critical_thinking",
                }
            }
        }
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _mock_response(search_payload),
            _mock_response(detail_payload),
        ]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.mcp.manager.httpx.AsyncClient", return_value=mock_client):
        raw = await _wikipedia_rest_search("critical thinking")

    data = json.loads(raw)
    assert len(data) == 1
    assert data[0]["title"] == "Critical thinking"
    assert "disciplined thinking" in data[0]["snippet"]
    findings = parse_web_findings(raw, "wikipedia")
    assert findings[0].url.endswith("Critical_thinking")


@pytest.mark.asyncio
async def test_duckduckgo_rest_search_uses_abstract_and_topics():
    payload = {
        "Heading": "Critical thinking",
        "AbstractText": "Critical thinking is the analysis of facts.",
        "AbstractURL": "https://duckduckgo.com/Critical_thinking",
        "RelatedTopics": [
            {"Text": "Logic - Study of reasoning", "FirstURL": "https://example.com/logic"},
        ],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(payload))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.mcp.manager.httpx.AsyncClient", return_value=mock_client):
        raw = await _duckduckgo_rest_search("critical thinking", limit=5)

    data = json.loads(raw)
    assert data[0]["title"] == "Critical thinking"
    assert any(item["title"] == "Logic" for item in data)
    findings = parse_web_findings(raw, "duckduckgo")
    assert len(findings) >= 2


def _mock_response(payload: dict):
    response = AsyncMock()
    response.raise_for_status = lambda: None
    response.json = lambda: payload
    return response
