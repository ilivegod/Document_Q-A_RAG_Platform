"""Sentry initialization for the backend.

Call init_sentry() once at process startup - from main.py for the API
process and from celery_app.py for the worker process. Each call is
idempotent, but calling once is cleaner.

If SENTRY_DSN is empty or missing, init is a no-op — local dev runs
without Sentry. No errors.
"""
import logging
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings

logger = logging.getLogger(__name__)


# Keys we never want in event payloads, regardless of where they appear
# (request body, breadcrumbs, extra context). Matched case-insensitively
# against dict keys in the before_send scrubber below.
_SENSITIVE_KEYS = frozenset(
    [
        "password",
        "new_password",
        "hashed_password",
        "token",
        "refresh_token",
        "access_token",
        "authorization",
        "api_key",
        "secret",
    ]
)


def _scrub(value: Any) -> Any:
    """Recursively replace values under sensitive keys with '[Filtered]'.

    Operates on the nested dict/list structures Sentry uses for event
    payloads. Leaves other types alone.
    """
    if isinstance(value, dict):
        return {
            k: ("[Filtered]" if k.lower() in _SENSITIVE_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _before_send(event: dict, _hint: dict) -> dict | None:
    """Last-mile scrubber. Sentry calls this for every event before send."""
    return _scrub(event)  # type: ignore[return-value]


def init_sentry() -> None:
    """Initialize Sentry. No-op if SENTRY_DSN is unset.

    Call once at process startup. Calling more than once is harmless but
    pointless — the SDK keeps the most recent config.
    """
    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured; skipping Sentry init")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Don't auto-attach user IP, cookies, headers with auth tokens, etc.
        # We add identity via set_user in middleware if/when we want it.
        send_default_pii=False,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            CeleryIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=_before_send,
    )
    logger.info(
        "Sentry initialized (env=%s, traces=%s)",
        settings.sentry_environment,
        settings.sentry_traces_sample_rate,
    )