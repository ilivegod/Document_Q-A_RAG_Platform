"""Map LLM provider errors to actionable HTTP responses."""
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_AI_STUDIO_KEY_HELP = (
    "Google API key is invalid. Set GOOGLE_API_KEY in .env to a key from "
    "Google AI Studio (https://aistudio.google.com/apikey), then restart "
    "Docker (api and celery_worker)."
)


def raise_llm_http_error(exc: Exception, *, action: str) -> None:
    """Raise HTTPException with a user-facing message for common LLM failures."""
    err = str(exc)
    lowered = err.lower()

    if "api_key_invalid" in lowered or "api key not valid" in lowered:
        raise HTTPException(status_code=503, detail=_AI_STUDIO_KEY_HELP) from exc

    if "429" in err or "resource_exhausted" in lowered:
        raise HTTPException(
            status_code=429,
            detail="LLM rate limit reached. Please wait and try again.",
        ) from exc

    logger.error("%s failed: %s", action, exc, exc_info=True)
    raise HTTPException(
        status_code=502,
        detail=f"Failed to {action}. Please try again.",
    ) from exc
