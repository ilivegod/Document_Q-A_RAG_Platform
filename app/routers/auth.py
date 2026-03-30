from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.models.user import User
from app.schemas.auth import UserResponse, UserCreate, Token, LoginRequest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies.getUser import get_user, authenticate_user
from app.utils.register import get_password_hash, create_access_token


router = APIRouter()


@router.post("/auth/register", response_model=UserResponse)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await get_user(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username, email=user.email, hashed_password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post("/auth/login", response_model=Token)
async def login_user(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
