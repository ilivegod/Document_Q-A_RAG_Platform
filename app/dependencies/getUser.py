from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from sqlalchemy import select
from app.utils.register import verify_password
from app.database import get_db
from app.schemas.auth import TokenData
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from app.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_user(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def _decode_token(token: str, expected_type: str) -> TokenData:
    """Decode a JWT and verify it has the expected type claim.
    Raises 401 on any failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        email: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if email is None or token_type != expected_type:
            raise credentials_exception

        return TokenData(email=email)
    except JWTError:
        raise credentials_exception


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    token_data = _decode_token(token, expected_type="access")
    user = await get_user(db, email=token_data.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_user_from_refresh_token(
    refresh_token: str,
    db: AsyncSession,
):
    """Validate a refresh token and return the associated user.
    Note: this is NOT a FastAPI dependency - it's called manually
    from the /auth/refresh endpoint with the token from the JSON body."""
    token_data = _decode_token(refresh_token, expected_type="refresh")
    user = await get_user(db, email=token_data.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user