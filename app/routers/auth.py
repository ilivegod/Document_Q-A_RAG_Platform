from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import User
from app.schemas.auth import UserResponse, UserCreate, Token, RefreshRequest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
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
)


router = APIRouter()


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