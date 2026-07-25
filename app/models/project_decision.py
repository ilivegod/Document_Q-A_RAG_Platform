from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enums):
    return [member.value for member in enums]


class DecisionCategory(str, Enum):
    ARCHITECTURE = "architecture"
    TECHNOLOGY = "technology"
    SCOPE = "scope"
    PROCESS = "process"
    OTHER = "other"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"


class ProjectDecision(Base):
    __tablename__ = "project_decisions"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    technology_exploration_id = mapped_column(
        UUID,
        ForeignKey("technology_explorations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = mapped_column(String(500), nullable=False)
    category: Mapped[DecisionCategory] = mapped_column(
        SQLEnum(
            DecisionCategory,
            name="decisioncategory",
            values_callable=_enum_values,
        ),
        default=DecisionCategory.TECHNOLOGY,
        nullable=False,
    )
    status: Mapped[DecisionStatus] = mapped_column(
        SQLEnum(
            DecisionStatus,
            name="decisionstatus",
            values_callable=_enum_values,
        ),
        default=DecisionStatus.PROPOSED,
        nullable=False,
    )
    context = mapped_column(Text, nullable=True)
    chosen_option = mapped_column(Text, nullable=False)
    alternatives_considered = mapped_column(JSONB, nullable=True)
    rationale = mapped_column(Text, nullable=True)
    consequences = mapped_column(JSONB, nullable=True)
    related_requirement_ids = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
