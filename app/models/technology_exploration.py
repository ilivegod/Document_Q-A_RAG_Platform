from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enums):
    return [member.value for member in enums]


class TechnologyExplorationStatus(str, Enum):
    COMPLETED = "completed"


class TechnologyExploration(Base):
    __tablename__ = "technology_explorations"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic = mapped_column(Text, nullable=False)
    status: Mapped[TechnologyExplorationStatus] = mapped_column(
        SQLEnum(
            TechnologyExplorationStatus,
            name="technologyexplorationstatus",
            values_callable=_enum_values,
        ),
        default=TechnologyExplorationStatus.COMPLETED,
        nullable=False,
    )
    analysis = mapped_column(JSONB, nullable=False)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
