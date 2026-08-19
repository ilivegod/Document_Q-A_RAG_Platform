"""Tests for contact email extraction from HTML."""

from app.services.contact_extraction import (
    extract_contact_email_from_pages,
    extract_emails_from_html,
    pick_best_contact_email,
)


def test_extract_emails_from_html_and_mailto():
    html = """
    <html><body>
      <a href="mailto:owner@acme.com">Email us</a>
      <p>Also reach sales@acme.com or noreply@acme.com</p>
    </body></html>
    """
    emails = extract_emails_from_html(html)
    assert "owner@acme.com" in emails
    assert "sales@acme.com" in emails


def test_pick_best_contact_email_prefers_non_generic():
    emails = ["noreply@acme.com", "owner@acme.com", "info@acme.com"]
    assert pick_best_contact_email(emails) == "owner@acme.com"


def test_extract_contact_email_from_pages_prefers_domain_match():
    homepage = "<p>hello@other.com</p>"
    contact = "<a href='mailto:ceo@dentist.com'>Contact</a>"
    assert extract_contact_email_from_pages(
        homepage,
        contact,
        "https://www.dentist.com",
    ) == "ceo@dentist.com"
