from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class BaselineStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class RequirementBaseline(Base):
    __tablename__ = "requirement_baselines"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = mapped_column(Integer, nullable=False)
    status: Mapped[BaselineStatus] = mapped_column(
        SQLEnum(
            BaselineStatus,
            name="baselinestatus",
            values_callable=_ENUM_VALUES,
        ),
        default=BaselineStatus.DRAFT,
        nullable=False,
    )
    label = mapped_column(String(255), nullable=True)
    snapshot = mapped_column(JSONB, nullable=False)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
