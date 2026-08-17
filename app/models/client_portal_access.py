"""Agency domain: tokenized client portal access per project."""

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientPortalAccess(Base):
    __tablename__ = "client_portal_access"

    id = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(
        UUID,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    token = mapped_column(String(64), nullable=False, unique=True, index=True)
    passcode_hash = mapped_column(String(255), nullable=True)
    can_submit_requests: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at = mapped_column(DateTime(timezone=True), nullable=True)
