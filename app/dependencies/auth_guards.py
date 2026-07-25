from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User

PENDING_APPROVAL_MESSAGE = (
    "Your account is pending approval. "
    "You'll be able to sign in after the admin approves your request."
)


def require_approved_user(user: User) -> None:
    """Block login/refresh when closed beta is on and user is not approved."""
    if settings.closed_beta_enabled and not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PENDING_APPROVAL_MESSAGE,
        )
