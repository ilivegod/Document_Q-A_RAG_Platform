from sqlalchemy.orm import mapped_column
from sqlalchemy import String, DateTime, func
from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid

class User(Base):
    __tablename__ = "user"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    username = mapped_column(String(50), nullable=False)
    email = mapped_column(String(50), nullable=False)
    hashed_password = mapped_column(String(255), nullable=False)
    created_at =mapped_column(DateTime,nullable=False, server_default=func.now())