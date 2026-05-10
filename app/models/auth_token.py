from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    func,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from enum import Enum
from datetime import datetime
import uuid


class TokenType(str, Enum):
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


class AuthToken(Base):
    """Single-use, server-side tokens for email-based auth flows.

    Used for password reset and email verification (and any future
    similar flows like magic links). The raw token is generated with
    secrets.token_urlsafe and only its SHA-256 hash is stored here —
    same principle as password hashing: a DB leak doesn't yield
    usable tokens.

    A token is valid iff:
        - the row exists
        - used_at IS NULL
        - expires_at > now()

    On successful use, used_at is set to mark the token consumed.
    Cleanup of expired/used rows is handled by a periodic Celery
    task (kept out of the request path).
    """

    __tablename__ = "auth_tokens"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_type: Mapped[TokenType] = mapped_column(
        SQLEnum(TokenType, name="tokentype"),
        nullable=False,
    )
    token_hash = mapped_column(String(64), nullable=False, unique=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Composite index for "find pending tokens for this user of this type".
    # Useful when invalidating all of a user's pending password resets after
    # a successful reset (defense in depth).
    __table_args__ = (
        Index(
            "ix_auth_tokens_user_type_used",
            "user_id",
            "token_type",
            "used_at",
        ),
    )