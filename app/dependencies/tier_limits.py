from fastapi import Depends, HTTPException

from app.dependencies.rate_limit import TIER_LIMITS
from app.dependencies.getUser import get_current_user
from app.models.user import User, UserTier


def get_tier_limits(user: User = Depends(get_current_user)) -> dict[str, str]:
    tier_key = user.tier.value if isinstance(user.tier, UserTier) else str(user.tier).lower()
    return TIER_LIMITS.get(tier_key, TIER_LIMITS["free"])


def require_pro_tier(user: User = Depends(get_current_user)) -> User:
    if user.tier == UserTier.FREE:
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Pro subscription. Upgrade to unlock all agent tools.",
        )
    return user
