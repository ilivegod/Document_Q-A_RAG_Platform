"""Tests for website audit heuristics."""

import pytest
from httpx import Response

from app.models.prospect import WebsiteStatus
from app.services.website_audit import audit_website


@pytest.mark.asyncio
async def test_audit_no_website():
    result = await audit_website(None)
    assert result.website_status == WebsiteStatus.NONE
    assert "No website listed" in result.audit_signals["signals"]


@pytest.mark.asyncio
async def test_audit_poor_thin_content(monkeypatch):
    async def fake_get(self, url, **kwargs):
        html = "<html><head><title>Hi</title></head><body>short</body></html>"
        return Response(200, text=html, request=None)

    monkeypatch.setattr(
        "httpx.AsyncClient.get",
        fake_get,
    )
    result = await audit_website("http://example.com")
    assert result.website_status == WebsiteStatus.POOR
    assert result.audit_signals["word_count"] < 80
