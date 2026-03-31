from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(
                f"Unhandled error: {str(e)} | Path: {request.url.path} | Method: {request.method}",
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error. Please try again later."},
            )
