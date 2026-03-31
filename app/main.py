from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from sqlalchemy import text
from app.routers.documents import router as documents_router
from app.routers.query import router as query_router
from app.routers.auth import router as auth_router
from app.middleware.error_handler import ErrorHandlerMiddleware
from fastapi.middleware.cors import CORSMiddleware

import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI()

app.include_router(documents_router)
app.include_router(query_router)
app.include_router(auth_router)

app.add_middleware(ErrorHandlerMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_okay = False
    try:
        await db.execute(text("SELECT 1"))
        db_okay = True
    except Exception:
        pass

    return "healthy" if db_okay else "not healthy"
