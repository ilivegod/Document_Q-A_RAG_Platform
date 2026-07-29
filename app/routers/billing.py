import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.models.user import User, UserTier

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


class CheckoutResponse(BaseModel):
    checkout_url: str | None
    message: str


class TierResponse(BaseModel):
    tier: str
    limits: dict[str, str]


@router.get("/tier", response_model=TierResponse)
async def get_my_tier(current_user: User = Depends(get_current_user)):
    from app.dependencies.rate_limit import TIER_LIMITS

    tier_key = current_user.tier.value
    return TierResponse(tier=tier_key, limits=TIER_LIMITS.get(tier_key, TIER_LIMITS["free"]))


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(current_user: User = Depends(get_current_user)):
    """Create a Stripe Checkout session for Pro upgrade.

    Requires STRIPE_SECRET_KEY and STRIPE_PRICE_ID_PRO in environment.
    """
    if not settings.stripe_secret_key or not settings.stripe_price_id_pro:
        return CheckoutResponse(
            checkout_url=None,
            message=(
                "Billing is not configured. Set STRIPE_SECRET_KEY and "
                "STRIPE_PRICE_ID_PRO to enable upgrades."
            ),
        )

    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.stripe_price_id_pro, "quantity": 1}],
            success_url=f"{settings.frontend_url}/projects?upgraded=1",
            cancel_url=f"{settings.frontend_url}/projects",
            client_reference_id=str(current_user.id),
            customer_email=current_user.email,
            metadata={"user_id": str(current_user.id)},
        )
        return CheckoutResponse(checkout_url=session.url, message="Redirect to checkout")
    except Exception as e:
        logger.error("Stripe checkout failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create checkout session")


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook to upgrade user tier on successful payment."""
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=501, detail="Webhooks not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception as e:
        logger.warning("Webhook verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session: dict[str, Any] = event["data"]["object"]
        user_id = session.get("client_reference_id") or (
            session.get("metadata") or {}
        ).get("user_id")
        if user_id:
            import uuid

            user = await db.get(User, uuid.UUID(user_id))
            if user:
                user.tier = UserTier.PRO
                await db.commit()
                logger.info("Upgraded user %s to PRO", user_id)

    return {"received": True}
