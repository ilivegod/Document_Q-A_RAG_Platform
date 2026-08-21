from enum import Enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

_ENUM_VALUES = lambda enums: [member.value for member in enums]


class ProjectType(str, Enum):
    CLIENT = "client"
    INDIE = "indie"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectAnalysisStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"


class PipelineStage(str, Enum):
    LEAD = "lead"
    PROPOSAL_SENT = "proposal_sent"
    IN_DEVELOPMENT = "in_development"
    QA_REVIEW = "qa_review"
    HANDED_OFF = "handed_off"


class Project(Base):
    __tablename__ = "projects"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = mapped_column(
        UUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)
    client_name = mapped_column(String(255), nullable=True)
    project_type: Mapped[ProjectType] = mapped_column(
        SQLEnum(
            ProjectType,
            name="projecttype",
            values_callable=_ENUM_VALUES,
        ),
        default=ProjectType.INDIE,
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(
            ProjectStatus,
            name="projectstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )
    analysis_status: Mapped[ProjectAnalysisStatus] = mapped_column(
        SQLEnum(
            ProjectAnalysisStatus,
            name="projectanalysisstatus",
            values_callable=_ENUM_VALUES,
        ),
        default=ProjectAnalysisStatus.IDLE,
        nullable=False,
    )
    requirements_extracted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    technology_generated: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    last_analyzed_at = mapped_column(DateTime(timezone=True), nullable=True)
    pipeline_stage: Mapped[PipelineStage] = mapped_column(
        SQLEnum(
            PipelineStage,
            name="pipelinestage",
            values_callable=_ENUM_VALUES,
        ),
        default=PipelineStage.LEAD,
        nullable=False,
        index=True,
    )
    prospect_id = mapped_column(
        UUID,
        ForeignKey("prospects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
