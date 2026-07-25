from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class RequirementCategory(str, Enum):
    FEATURE = "feature"
    CONSTRAINT = "constraint"
    INTEGRATION = "integration"
    NON_FUNCTIONAL = "non_functional"
    ASSUMPTION = "assumption"
    RISK = "risk"
    OPEN_QUESTION = "open_question"


class RequirementPriority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    UNKNOWN = "unknown"


class RequirementStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Requirement(Base):
    __tablename__ = "requirements"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stable_id = mapped_column(String(32), nullable=False)
    title = mapped_column(String(500), nullable=False)
    description = mapped_column(Text, nullable=True)
    category: Mapped[RequirementCategory] = mapped_column(
        SQLEnum(
            RequirementCategory,
            name="requirementcategory",
            values_callable=_ENUM_VALUES,
        ),
        nullable=False,
    )
    priority: Mapped[RequirementPriority] = mapped_column(
        SQLEnum(
            RequirementPriority,
            name="requirementpriority",
            values_callable=_ENUM_VALUES,
        ),
        default=RequirementPriority.UNKNOWN,
        nullable=False,
    )
    status: Mapped[RequirementStatus] = mapped_column(
        SQLEnum(
            RequirementStatus,
            name="requirementstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=RequirementStatus.PROPOSED,
        nullable=False,
    )
    acceptance_criteria = mapped_column(JSONB, nullable=True)
    assumptions = mapped_column(JSONB, nullable=True)
    source_refs = mapped_column(JSONB, nullable=True)
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
