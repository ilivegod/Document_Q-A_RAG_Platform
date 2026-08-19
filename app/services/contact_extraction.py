"""Extract contact emails from business websites."""

from __future__ import annotations

import re
from urllib.parse import urljoin

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.I,
)


def extract_emails_from_html(html: str) -> list[str]:
    found: list[str] = []
    for match in EMAIL_PATTERN.findall(html):
        email = match.lower().strip()
        if email.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if "example.com" in email or "sentry.io" in email:
            continue
        if email not in found:
            found.append(email)
    for mailto in re.findall(r"mailto:([^\"'?>\s]+)", html, re.I):
        email = mailto.split("?")[0].strip().lower()
        if email and email not in found:
            found.append(email)
    return found


def pick_best_contact_email(emails: list[str]) -> str | None:
    if not emails:
        return None
    generic_prefixes = ("noreply", "no-reply", "donotreply", "support", "sales")
    for email in emails:
        local = email.split("@")[0]
        if not any(local.startswith(p) for p in generic_prefixes):
            return email
    return emails[0]


def _domain_from_url(url: str) -> str:
    domain = url.split("//")[-1].split("/")[0].lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_contact_email_from_pages(
    homepage_html: str,
    contact_html: str | None = None,
    website_url: str | None = None,
) -> str | None:
    emails = extract_emails_from_html(homepage_html)
    if contact_html:
        emails.extend(extract_emails_from_html(contact_html))
    if website_url:
        domain = _domain_from_url(website_url)
        domain_emails = [
            e for e in emails if domain in e.split("@")[-1] or e.endswith(f"@{domain}")
        ]
        if domain_emails:
            return pick_best_contact_email(domain_emails)
    return pick_best_contact_email(emails)
