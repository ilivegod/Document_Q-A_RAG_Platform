"""Lightweight website quality audit for prospect scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.models.prospect import WebsiteStatus

MAX_BYTES = 500_000
TIMEOUT = 8.0
USER_AGENT = "ShioriProspectBot/1.0 (+https://shiori.app)"


@dataclass
class WebsiteAuditResult:
    website_status: WebsiteStatus
    audit_signals: dict
    homepage_text: str
    homepage_html: str = ""
    contact_html: str = ""


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        return f"https://{url.strip()}"
    return url.strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()[:200]


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def _fetch_url(client: httpx.AsyncClient, url: str) -> tuple[int | None, str, bool]:
    try:
        response = await client.get(url, follow_redirects=True)
        content = response.text[:MAX_BYTES] if response.text else ""
        return response.status_code, content, url.lower().startswith("https")
    except Exception:
        return None, "", False


async def audit_website(website_url: str | None) -> WebsiteAuditResult:
    if not website_url or not website_url.strip():
        return WebsiteAuditResult(
            website_status=WebsiteStatus.NONE,
            audit_signals={
                "signals": ["No website listed"],
                "https": False,
                "status_code": None,
                "word_count": 0,
            },
            homepage_text="",
            homepage_html="",
        )

    url = _normalize_url(website_url)
    signals: list[str] = []

    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        status_code, html, https = await _fetch_url(client, url)
        contact_url = urljoin(url, "/contact")
        contact_status, contact_html, _ = await _fetch_url(client, contact_url)

    if status_code is None:
        return WebsiteAuditResult(
            website_status=WebsiteStatus.POOR,
            audit_signals={
                "signals": ["Website unreachable"],
                "https": False,
                "status_code": None,
                "word_count": 0,
                "has_contact_page": False,
            },
            homepage_text="",
            homepage_html="",
        )

    title = _extract_title(html) or ""
    text = _strip_html(html)
    word_count = _word_count(text)
    has_contact_page = contact_status == 200 and len(contact_html) > 100

    if not https:
        signals.append("No HTTPS")
    if status_code >= 400:
        signals.append(f"HTTP {status_code}")
    if word_count < 80:
        signals.append("Very thin homepage content")
    if not title:
        signals.append("Missing page title")
    if re.search(r"coming soon|under construction|parked domain", text, re.I):
        signals.append("Parked or coming-soon page")
    if re.search(r"wix\.com|squarespace|godaddy", url, re.I):
        signals.append("Generic website builder URL")

    website_status = WebsiteStatus.OK
    if not https or word_count < 80 or status_code >= 400 or len(signals) >= 2:
        website_status = WebsiteStatus.POOR

    return WebsiteAuditResult(
        website_status=website_status,
        audit_signals={
            "signals": signals,
            "https": https,
            "status_code": status_code,
            "word_count": word_count,
            "has_contact_page": has_contact_page,
            "title": title,
        },
        homepage_text=text[:3000],
        homepage_html=html[:MAX_BYTES],
        contact_html=contact_html[:3000] if contact_html else "",
    )
