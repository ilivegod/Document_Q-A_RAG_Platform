"""Email service. Resend SDK is sync, so each send is run in a thread
to avoid blocking the event loop (same pattern as embedding.py).
"""
import asyncio
import logging
from typing import Any

import resend

from app.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


def _send_sync(to: str, subject: str, html: str, text: str) -> dict[str, Any]:
    return resend.Emails.send(
        {
            "from": settings.email_from,
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
        }
    )


async def _send(to: str, subject: str, html: str, text: str) -> None:
    try:
        result = await asyncio.to_thread(_send_sync, to, subject, html, text)
        logger.info("Sent email to %s (id=%s)", to, result.get("id"))
    except Exception:
        logger.exception("Failed to send email to %s", to)


async def send_password_reset_email(to: str, username: str, reset_url: str) -> None:
    subject = "Reset your Shiori password"
    text = (
        f"Hi {username},\n\n"
        "Someone (hopefully you) requested a password reset for your Shiori account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        f"This link expires in {settings.password_reset_ttl_minutes} minutes.\n\n"
        "If you didn't request this, ignore this email; your password won't change.\n\n"
        "— Shiori"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #222;">
  <p>Hi {username},</p>
  <p>Someone (hopefully you) requested a password reset for your Shiori account.</p>
  <p><a href="{reset_url}" style="display: inline-block; padding: 10px 16px; background: #111; color: #fff; text-decoration: none; border-radius: 6px;">Reset your password</a></p>
  <p style="color: #666; font-size: 14px;">Or copy this link: <br><a href="{reset_url}">{reset_url}</a></p>
  <p style="color: #666; font-size: 14px;">This link expires in {settings.password_reset_ttl_minutes} minutes.</p>
  <p style="color: #666; font-size: 14px;">If you didn't request this, ignore this email — your password won't change.</p>
  <p style="color: #999; font-size: 12px;">— Shiori</p>
</body></html>"""
    await _send(to, subject, html, text)


async def send_verification_email(to: str, username: str, verify_url: str) -> None:
    subject = "Verify your Shiori email"
    text = (
        f"Hi {username},\n\n"
        "Welcome to Shiori. Please verify your email address:\n\n"
        f"{verify_url}\n\n"
        "— Shiori"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #222;">
  <p>Hi {username},</p>
  <p>Welcome to Shiori. Please verify your email address:</p>
  <p><a href="{verify_url}" style="display: inline-block; padding: 10px 16px; background: #111; color: #fff; text-decoration: none; border-radius: 6px;">Verify email</a></p>
  <p style="color: #666; font-size: 14px;">Or copy this link: <br><a href="{verify_url}">{verify_url}</a></p>
  <p style="color: #999; font-size: 12px;">— Shiori</p>
</body></html>"""
    await _send(to, subject, html, text)


async def send_admin_signup_email(
    admin_to: str,
    user_email: str,
    username: str,
    approve_url: str,
) -> None:
    subject = f"Shiori: Approve signup for {user_email}"
    text = (
        f"A new user requested access to Shiori.\n\n"
        f"Username: {username}\n"
        f"Email: {user_email}\n\n"
        f"Approve this account:\n{approve_url}\n\n"
        f"This link expires in {settings.admin_approval_ttl_days} days.\n\n"
        "— Shiori"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #222;">
  <p>A new user requested access to <strong>Shiori</strong>.</p>
  <ul>
    <li><strong>Username:</strong> {username}</li>
    <li><strong>Email:</strong> {user_email}</li>
  </ul>
  <p><a href="{approve_url}" style="display: inline-block; padding: 10px 16px; background: #111; color: #fff; text-decoration: none; border-radius: 6px;">Approve account</a></p>
  <p style="color: #666; font-size: 14px;">Or copy this link:<br><a href="{approve_url}">{approve_url}</a></p>
  <p style="color: #666; font-size: 14px;">Expires in {settings.admin_approval_ttl_days} days.</p>
  <p style="color: #999; font-size: 12px;">— Shiori</p>
</body></html>"""
    await _send(admin_to, subject, html, text)


async def send_account_approved_email(to: str, username: str, login_url: str) -> None:
    subject = "Your Shiori account has been approved"
    text = (
        f"Hi {username},\n\n"
        "Your Shiori account has been approved. You can now sign in:\n\n"
        f"{login_url}\n\n"
        "— Shiori"
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5; color: #222;">
  <p>Hi {username},</p>
  <p>Your Shiori account has been <strong>approved</strong>. You can now sign in and use the app.</p>
  <p><a href="{login_url}" style="display: inline-block; padding: 10px 16px; background: #111; color: #fff; text-decoration: none; border-radius: 6px;">Sign in</a></p>
  <p style="color: #999; font-size: 12px;">— Shiori</p>
</body></html>"""
    await _send(to, subject, html, text)
