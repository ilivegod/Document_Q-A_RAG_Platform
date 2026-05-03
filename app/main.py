from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.database import get_db
from app.config import settings
from app.routers.documents import router as documents_router
from app.routers.query import router as query_router
from app.routers.auth import router as auth_router
from app.middleware.error_handler import ErrorHandlerMiddleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


app = FastAPI(title="DocQA API")

app.include_router(documents_router)
app.include_router(query_router)
app.include_router(auth_router)

app.add_middleware(ErrorHandlerMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health/live")
async def liveness():
    """Liveness probe — is the process alive?
    No dependency checks. If this responds, the process is up."""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness probe — is the app ready to serve traffic?
    Checks DB connectivity. Returns 503 if dependencies are down."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "error"},
        )


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Combined health check (kept for backwards compatibility)."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"},
        )