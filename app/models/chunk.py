from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB

from pgvector.sqlalchemy import Vector
import uuid
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Chunk(Base):
    __tablename__ = "chunk"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    page_num = Column(Integer, nullable=False)
    start_char = Column(Integer)
    end_char = Column(Integer)

    # NEW: list of bboxes in browser space (origin top-left, y grows down).
    # Each bbox is [x0, y0, x1, y1]. One chunk can span multiple lines, so
    # we store one bbox per line. NULL for chunks parsed before this field
    # existed (highlighting unavailable for those).
    bboxes = Column(JSONB, nullable=True)

    # NEW: page dimensions in points, needed by the frontend to scale
    # bbox coordinates relative to the rendered PDF page size.
    page_width = Column(Integer, nullable=True)
    page_height = Column(Integer, nullable=True)

