from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import settings

print(f"DEBUG: Database URL is -> {settings.database_url}")
engine = create_async_engine(settings.database_url)

async_session = async_sessionmaker(engine)

class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
