"""Rate limiting setup using slowapi with Redis backend.

Two key functions are used to identify clients:
- get_remote_address: from slowapi, uses the request's IP. Used for
  unauthenticated endpoints (login, register, refresh).
- get_user_id_key: extracts the user ID from the Authorization header.
  Used for authenticated endpoints (upload, query).

For per-email rate limiting (e.g. forgot-password), see the inline check
in the route handler — slowapi decorators run before the body is parsed,
so the email isn't available as a key_func at decorator time.

Limits are defined as constants here so adjusting them is one place to look.
When tiers are activated, the per-tier limits live in TIER_LIMITS below.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from jose import jwt, JWTError

from app.config import settings


# --- Rate limit constants ---
# Unauthenticated endpoints (keyed by IP)
LOGIN_LIMIT = "5/15minute"
REGISTER_LIMIT = "3/hour"
REFRESH_LIMIT = "10/minute"

# Password reset:
# - per-IP limit prevents bulk abuse from a single source
# - per-email limit prevents bombarding a single user's inbox
FORGOT_PASSWORD_IP_LIMIT = "10/hour"
FORGOT_PASSWORD_EMAIL_LIMIT = "3/hour"
RESET_PASSWORD_LIMIT = "5/hour"

# Email verification:
# - verify-email is per-IP (token does the real protection)
# - resend-verification is per-user (authenticated) to bound inbox spam
VERIFY_EMAIL_LIMIT = "10/hour"
RESEND_VERIFICATION_LIMIT = "3/hour"

# Authenticated endpoints (keyed by user ID)
# These currently apply to all users regardless of tier.
# When tier-based limits are activated, lookup TIER_LIMITS[user.tier] instead.
UPLOAD_LIMIT = "5/hour"
QUERY_LIMIT = "50/day"


# Future: tier-aware limits.
# Wired in when paid tiers are activated.
TIER_LIMITS = {
    "free": {
        "upload": "5/hour",
        "query": "50/day",
    },
    "pro": {
        "upload": "20/hour",
        "query": "500/day",
    },
    "business": {
        "upload": "50/hour",
        "query": "5000/day",
    },
}


def get_user_id_key(request: Request) -> str:
    """Extract user ID from the Authorization header for rate limiting.

    Falls back to IP address if no valid token is present (e.g. the request
    will be rejected by auth anyway, but we still want to rate-limit by
    something meaningful).

    Note: this function decodes the JWT but does NOT verify the user
    exists in the DB. That's fine for rate limiting — the actual auth
    dependency handles the full validation.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return get_remote_address(request)

    token = auth_header[7:].strip()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        # Use email as the key — it's stable, unique, and present in our tokens.
        # We could use 'sub' which is the same value.
        email = payload.get("sub")
        if email:
            return f"user:{email}"
    except JWTError:
        pass

    # Fallback: rate-limit by IP if token is malformed/expired
    return get_remote_address(request)


# The actual limiter instance. Stored on the FastAPI app and used as a
# decorator on routes.
#
# storage_uri uses Redis so counters persist across processes and restarts.
# Without this, in-memory storage would mean each worker has its own counts
# and limits could be bypassed by hitting different workers.
limiter = Limiter(
    key_func=get_remote_address,  # Default key func; overridden per-route via key_func= when needed
    storage_uri=settings.redis_url,
    strategy="fixed-window",  # Simple, predictable. Alternatives: moving-window, sliding-window.
)