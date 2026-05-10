from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from limits import parse as parse_limit

from app.models.user import User
from app.models.auth_token import TokenType
from app.schemas.auth import (
    UserResponse,
    UserCreate,
    Token,
    RefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.dependencies.getUser import (
    get_user,
    authenticate_user,
    get_current_user,
    get_user_from_refresh_token,
)
from app.utils.register import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
)
from app.dependencies.rate_limit import (
    limiter,
    LOGIN_LIMIT,
    REGISTER_LIMIT,
    REFRESH_LIMIT,
    FORGOT_PASSWORD_IP_LIMIT,
    FORGOT_PASSWORD_EMAIL_LIMIT,
    RESET_PASSWORD_LIMIT,
)
from app.services.token_service import (
    create_token,
    consume_token,
    invalidate_user_tokens,
)
from app.services.email import send_password_reset_email


router = APIRouter()


# Pre-parsed limit item for the per-email check on forgot-password.
# Parsed once at import time, used inline below via limiter.limiter.hit().
_FORGOT_PW_EMAIL_LIMIT_ITEM = parse_limit(FORGOT_PASSWORD_EMAIL_LIMIT)

_UNIFORM_FORGOT_RESPONSE = MessageResponse(
    message="If an account exists for that email, a password reset link has been sent."
)


@router.post("/auth/register", response_model=UserResponse)
@limiter.limit(REGISTER_LIMIT)
async def register_user(
    request: Request,
    user: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    db_user = await get_user(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post("/auth/login", response_model=Token)
@limiter.limit(LOGIN_LIMIT)
async def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/auth/refresh", response_model=Token)
@limiter.limit(REFRESH_LIMIT)
async def refresh_access_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_refresh_token(body.refresh_token, db)
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/auth/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/auth/forgot-password", response_model=MessageResponse)
@limiter.limit(FORGOT_PASSWORD_IP_LIMIT)
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Issue a password reset token and email it to the user.

    Always returns the same response regardless of whether the email
    exists, to prevent account enumeration.

    Two rate limits apply: per-IP (decorator above) bounds bulk abuse;
    per-email (checked manually below) bounds inbox-bombing of a single
    account. The per-email check is applied here in the body rather than
    via decorator because slowapi decorators run before the request body
    is parsed.
    """
    # Per-email rate limit check. Uses the limits library directly through
    # the slowapi limiter's underlying strategy. Same Redis storage as the
    # decorator-based limits.
    email_key = f"forgot-pw-email:{body.email.lower()}"
    allowed = limiter.limiter.hit(_FORGOT_PW_EMAIL_LIMIT_ITEM, email_key)
    if not allowed:
        # Match the response shape slowapi uses for decorator-triggered
        # limits (429 with a detail message). The actual quota numbers
        # aren't leaked.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests for this email. Try again later.",
        )

    user = await get_user(db, email=body.email)
    if user is None:
        return _UNIFORM_FORGOT_RESPONSE

    raw_token = await create_token(
        db,
        user_id=user.id,
        token_type=TokenType.PASSWORD_RESET,
        ttl_minutes=settings.password_reset_ttl_minutes,
    )
    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"

    await send_password_reset_email(
        to=user.email,
        username=user.username,
        reset_url=reset_url,
    )

    return _UNIFORM_FORGOT_RESPONSE


@router.post("/auth/reset-password", response_model=MessageResponse)
@limiter.limit(RESET_PASSWORD_LIMIT)
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Consume a password reset token and set the new password.

    Token is single-use, atomic. On success, any other pending reset
    tokens for this user are invalidated as defense in depth.

    NOTE: This does NOT invalidate active sessions. Refresh tokens are
    stateless JWTs with no revocation mechanism. When refresh token
    revocation is added, kill all of this user's refresh tokens here.
    """
    user = await consume_token(
        db,
        raw_token=body.token,
        expected_type=TokenType.PASSWORD_RESET,
    )

    user.hashed_password = get_password_hash(body.new_password)
    await db.commit()

    await invalidate_user_tokens(
        db,
        user_id=user.id,
        token_type=TokenType.PASSWORD_RESET,
    )

    return MessageResponse(message="Password reset successfully")