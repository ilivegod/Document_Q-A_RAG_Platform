from sqlalchemy.orm import mapped_column
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text
from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import VECTOR
import uuid

class Chunk(Base):
    __tablename__ = "chunk"

    id = mapped_column(UUID, primary_key=True,default=uuid.uuid4)
    doc_id = mapped_column(UUID, ForeignKey("documents.id"), nullable=False)
    content = mapped_column(Text(), nullable=False)
    chunk_index = mapped_column(Integer(), nullable=False)
    page_num = mapped_column(Integer(), nullable=True)
    start_char = mapped_column(Integer(), nullable=True)
    end_char = mapped_column(Integer(), nullable=True)
    embedding = mapped_column(VECTOR(384))









