from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.schemas import WebFinding


@dataclass
class AgentContext:
    """Runtime context passed to every tool handler."""

    db: AsyncSession
    user_id: UUID
    document_id: UUID | None = None
    project_id: UUID | None = None
    collected_chunks: list = field(default_factory=list)
    collected_web_sources: list[WebFinding] = field(default_factory=list)
    last_web_sub_steps: list = field(default_factory=list)
