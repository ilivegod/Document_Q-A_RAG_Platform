"""Google Places discovery for local business prospects."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
PLACES_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DEFAULT_MAX_CANDIDATES = 15
MAX_CANDIDATES = DEFAULT_MAX_CANDIDATES


def _places_user_message(status: str, error_message: str = "") -> str:
    if status == "REQUEST_DENIED":
        return (
            "Google Places access was denied. Check GOOGLE_PLACES_API_KEY and that "
            "Places API is enabled for your Google Cloud project."
        )
    if status == "OVER_QUERY_LIMIT":
        return "Google Places quota exceeded. Wait a few minutes and try again."
    if status == "INVALID_REQUEST":
        return (
            "Google Places could not run this search. Try a simpler location, "
            "fewer max leads, or search again in a moment."
        )
    if status == "ZERO_RESULTS":
        return "No businesses matched this search."
    if error_message:
        return f"Google Places error ({status}): {error_message}"
    return f"Google Places error: {status}"


def _places_key() -> str:
    key = settings.google_places_api_key or settings.google_api_key
    return key


async def autocomplete_locations(input_text: str) -> list[dict[str, str]]:
    """Return location suggestions for the leads search form."""
    query = input_text.strip()
    if len(query) < 2:
        return []

    api_key = _places_key()
    if not api_key or api_key == "test-key":
        return []

    params = {
        "input": query,
        "types": "(regions)",
        "key": api_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(PLACES_AUTOCOMPLETE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(
                "Places autocomplete error: %s %s",
                payload.get("status"),
                payload.get("error_message", ""),
            )
            return []

        suggestions: list[dict[str, str]] = []
        for prediction in payload.get("predictions", [])[:8]:
            description = prediction.get("description")
            if not description:
                continue
            suggestions.append(
                {
                    "description": description,
                    "place_id": prediction.get("place_id", ""),
                }
            )
        return suggestions


async def fetch_place_candidates(
    location_query: str,
    industry_keywords: str,
    radius_km: int,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Return up to max_candidates place stubs from Google Places text search."""
    api_key = _places_key()
    if not api_key or api_key == "test-key":
        raise ValueError(
            "GOOGLE_PLACES_API_KEY (or GOOGLE_API_KEY) is required for prospect search"
        )

    limit = max(15, min(max_candidates, 50))
    query = f"{industry_keywords} in {location_query}"
    radius_m = max(1000, min(radius_km * 1000, 50000))

    candidates: list[dict[str, Any]] = []
    next_page_token: str | None = None
    pagination_retries = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(candidates) < limit:
            is_pagination = bool(next_page_token)
            if is_pagination:
                await asyncio.sleep(2.5 if pagination_retries == 0 else 4.0)

            if next_page_token:
                params = {"pagetoken": next_page_token, "key": api_key}
            else:
                params = {
                    "query": query,
                    "radius": radius_m,
                    "key": api_key,
                }

            response = await client.get(PLACES_TEXT_SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status")
            error_message = payload.get("error_message", "")

            if status == "ZERO_RESULTS":
                break

            if status != "OK":
                if (
                    is_pagination
                    and status == "INVALID_REQUEST"
                    and pagination_retries < 1
                ):
                    pagination_retries += 1
                    logger.warning(
                        "Places pagination not ready yet; retrying (%s)",
                        error_message,
                    )
                    continue
                if is_pagination and status == "INVALID_REQUEST" and candidates:
                    logger.warning(
                        "Places pagination failed; continuing with %d result(s): %s",
                        len(candidates),
                        error_message,
                    )
                    break
                raise ValueError(_places_user_message(status, error_message))

            pagination_retries = 0

            for place in payload.get("results", []):
                if len(candidates) >= limit:
                    break
                place_id = place.get("place_id")
                if not place_id:
                    continue
                candidates.append(
                    {
                        "place_id": place_id,
                        "business_name": place.get("name", "Unknown"),
                        "address": place.get("formatted_address"),
                    }
                )

            next_page_token = payload.get("next_page_token")
            if not next_page_token:
                break

        return candidates


async def enrich_place_candidate(
    place_id: str,
    fallback_name: str,
    fallback_address: str | None,
) -> dict[str, Any]:
    """Fetch phone and website for a single place."""
    api_key = _places_key()
    async with httpx.AsyncClient(timeout=30.0) as client:
        details = await _fetch_place_details(client, place_id, api_key)
        return {
            "place_id": place_id,
            "business_name": details.get("name") or fallback_name,
            "address": details.get("formatted_address") or fallback_address,
            "phone": details.get("formatted_phone_number"),
            "website_url": details.get("website"),
        }


async def search_places(
    location_query: str,
    industry_keywords: str,
    radius_km: int,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Legacy batch enrich — used only if callers need all places at once."""
    candidates = await fetch_place_candidates(
        location_query, industry_keywords, radius_km, max_candidates
    )
    enriched: list[dict[str, Any]] = []
    for c in candidates:
        enriched.append(
            await enrich_place_candidate(
                c["place_id"], c["business_name"], c.get("address")
            )
        )
    return enriched


async def _fetch_place_details(
    client: httpx.AsyncClient,
    place_id: str,
    api_key: str,
) -> dict[str, Any]:
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website",
        "key": api_key,
    }
    response = await client.get(PLACES_DETAILS_URL, params=params)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "OK":
        logger.warning("Place details failed for %s: %s", place_id, payload.get("status"))
        return {}
    return payload.get("result", {})
