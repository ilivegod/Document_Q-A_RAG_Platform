"""Google Places discovery for local business prospects."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
MAX_RESULTS = 20


def _places_key() -> str:
    key = settings.google_places_api_key or settings.google_api_key
    return key


async def search_places(
    location_query: str,
    industry_keywords: str,
    radius_km: int,
) -> list[dict[str, Any]]:
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
            raise ValueError(f"Places API error: {payload.get('status')} {payload.get('error_message', '')}")

        results = payload.get("results", [])[:MAX_RESULTS]
        enriched: list[dict[str, Any]] = []

        for place in results:
            place_id = place.get("place_id")
            if not place_id:
                continue
            details = await _fetch_place_details(client, place_id, api_key)
            enriched.append(
                {
                    "place_id": place_id,
                    "business_name": details.get("name") or place.get("name", "Unknown"),
                    "address": details.get("formatted_address") or place.get("formatted_address"),
                    "phone": details.get("formatted_phone_number"),
                    "website_url": details.get("website"),
                }
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
