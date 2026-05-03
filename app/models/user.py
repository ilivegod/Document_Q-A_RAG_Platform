from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import String, DateTime, func, Enum as SQLEnum
from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum
import uuid


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


class User(Base):
    __tablename__ = "user"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    username = mapped_column(String(50), nullable=False)
    email = mapped_column(String(254), nullable=False, unique=True, index=True)
    hashed_password = mapped_column(String(255), nullable=False)
    tier: Mapped[UserTier] = mapped_column(
        SQLEnum(UserTier),
        default=UserTier.FREE,
        nullable=False,
    )
    created_at = mapped_column(DateTime, nullable=False, server_default=func.now())