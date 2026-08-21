from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from app.sentry import init_sentry
init_sentry()

from app.database import get_db
from app.config import settings
from app.routers.documents import router as documents_router
from app.routers.auth import router as auth_router
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.dependencies.rate_limit import limiter
from app.routers.conversations import router as conversations_router
from app.routers.agent import router as agent_router
from app.routers.billing import router as billing_router
from app.routers.projects import router as projects_router
from app.routers.requirements import router as requirements_router
from app.routers.technology import router as technology_router
from app.routers.execution import router as execution_router
from app.routers.delivery import router as delivery_router
from app.routers.sow import router as sow_router
from app.routers.public_portal import router as public_portal_router
from app.routers.scope_changes import router as scope_changes_router
from app.routers.agency import router as agency_router
from app.routers.prospecting import router as prospecting_router
from app.routers.outreach import router as outreach_router
from app.routers.sales_proposals import router as sales_proposals_router




logger = logging.getLogger(__name__)


app = FastAPI(title="Shiori API")

# Attach the limiter to app state and register the 429 handler.
# Both are required for slowapi to function.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(agent_router)
app.include_router(billing_router)
app.include_router(projects_router)
app.include_router(requirements_router)
app.include_router(technology_router)
app.include_router(execution_router)
app.include_router(delivery_router)
app.include_router(sow_router)
app.include_router(public_portal_router)
app.include_router(scope_changes_router)
app.include_router(agency_router)
app.include_router(prospecting_router)
app.include_router(outreach_router)
app.include_router(sales_proposals_router)

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