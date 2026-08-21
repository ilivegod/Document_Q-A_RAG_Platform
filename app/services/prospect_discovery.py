"""Google Places discovery for local business prospects."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
PLACES_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
MAX_CANDIDATES = 10


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
) -> list[dict[str, Any]]:
    """Return up to MAX_CANDIDATES place stubs from Google Places text search."""
    api_key = _places_key()
    if not api_key or api_key == "test-key":
        raise ValueError(
            "GOOGLE_PLACES_API_KEY (or GOOGLE_API_KEY) is required for prospect search"
        )

    query = f"{industry_keywords} in {location_query}"
    radius_m = max(1000, min(radius_km * 1000, 50000))

    params = {
        "query": query,
        "radius": radius_m,
        "key": api_key,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(PLACES_TEXT_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in ("OK", "ZERO_RESULTS"):
            raise ValueError(
                f"Places API error: {payload.get('status')} "
                f"{payload.get('error_message', '')}"
            )

        candidates: list[dict[str, Any]] = []
        for place in payload.get("results", [])[:MAX_CANDIDATES]:
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
) -> list[dict[str, Any]]:
    """Legacy batch enrich — used only if callers need all places at once."""
    candidates = await fetch_place_candidates(
        location_query, industry_keywords, radius_km
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
