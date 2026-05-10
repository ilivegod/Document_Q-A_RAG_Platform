from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from .config import settings
import logging

logger = logging.getLogger(__name__)


logger.info("Initializing database engine")

engine = create_async_engine(settings.database_url)

# expire_on_commit=False keeps ORM attributes loaded across commits.
#
# The default (True) expires every attribute on every commit, forcing the
# next attribute read to re-query the DB. In async sessions this requires
# the greenlet context, which doesn't exist outside an awaited block —
# leading to MissingGreenlet crashes when ORM objects are accessed (e.g.
# for response serialization or follow-up logic) after a commit.
#
# Setting this False trades freshness for predictability. For request-scoped
# sessions in a web app this is the right tradeoff: each request gets its
# own session, and within one request you rarely care about other-session
# updates between your own commits.
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session