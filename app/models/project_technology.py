from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enums):
    return [member.value for member in enums]


class TechnologyCategory(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    AI = "ai"
    AUTHENTICATION = "authentication"
    HOSTING = "hosting"
    STORAGE = "storage"
    TESTING = "testing"
    PAYMENTS = "payments"
    DEVOPS = "devops"
    OTHER = "other"


class TechnologySource(str, Enum):
    AI = "ai"
    MANUAL = "manual"


class ProjectTechnology(Base):
    __tablename__ = "project_technologies"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_id = mapped_column(String(64), nullable=False)
    category: Mapped[TechnologyCategory] = mapped_column(
        SQLEnum(
            TechnologyCategory,
            name="technologycategory",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    source: Mapped[TechnologySource] = mapped_column(
        SQLEnum(
            TechnologySource,
            name="technologysource",
            values_callable=_enum_values,
        ),
        default=TechnologySource.MANUAL,
        nullable=False,
    )
    rationale = mapped_column(Text, nullable=True)
    sort_order = mapped_column(Integer, default=0, nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
