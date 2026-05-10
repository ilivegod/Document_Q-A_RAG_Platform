"""Token service for email-based auth flows (password reset, email verification).

Raw tokens are generated server-side, sent to users via email, and only
their SHA-256 hash is stored in the DB. Tokens are single-use: consume
marks used_at atomically.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_token import AuthToken, TokenType
from app.models.user import User

logger = logging.getLogger(__name__)


def _hash_token(raw: str) -> str:
    """SHA-256 hex digest. 64 chars, matches token_hash column width."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def create_token(
    db: AsyncSession,
    user_id: UUID,
    token_type: TokenType,
    ttl_minutes: int,
) -> str:
    """Generate a token, store its hash, return the raw token to the caller.

    Caller is responsible for embedding the raw token in the email URL.
    After this returns, the raw token only exists in the email — the DB
    has only the hash.
    """
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    db.add(
        AuthToken(
            user_id=user_id,
            token_type=token_type,
            token_hash=_hash_token(raw_token),
            expires_at=expires_at,
        )
    )
    await db.commit()

    logger.info(
        "Created %s token for user %s (ttl=%dmin)",
        token_type.value,
        user_id,
        ttl_minutes,
    )
    return raw_token


async def consume_token(
    db: AsyncSession,
    raw_token: str,
    expected_type: TokenType,
) -> User:
    """Validate and atomically mark token as used. Return the associated User.

    Raises 400 with a uniform message on any failure (wrong token, wrong
    type, expired, already used) — never leak which.
    """
    invalid = HTTPException(status_code=400, detail="Invalid or expired token")

    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    # Atomic: only one concurrent request can flip used_at from NULL to a value.
    stmt = (
        update(AuthToken)
        .where(
            AuthToken.token_hash == token_hash,
            AuthToken.token_type == expected_type,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(AuthToken.user_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        await db.rollback()
        logger.warning("Failed to consume %s token (hash=%s...)", expected_type.value, token_hash[:8])
        raise invalid

    user_id = row[0]
    user = await db.get(User, user_id)
    if user is None:
        # Token referenced a deleted user. CASCADE should prevent this,
        # but handle defensively.
        await db.rollback()
        logger.error("Consumed token for missing user %s", user_id)
        raise invalid

    await db.commit()
    return user


async def invalidate_user_tokens(
    db: AsyncSession,
    user_id: UUID,
    token_type: TokenType,
) -> None:
    """Mark all of a user's pending tokens of a given type as used.

    Called after a successful password reset to kill any other in-flight
    reset tokens (defense in depth).
    """
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.token_type == token_type,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    await db.commit()