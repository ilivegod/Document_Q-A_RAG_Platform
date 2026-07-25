"""Change impact analyzer tests."""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(auth_client: AsyncClient) -> str:
    r = await auth_client.post(
        "/projects",
        json={"name": f"Change test {uuid.uuid4().hex[:6]}", "project_type": "indie"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_analyze_requires_baseline(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/change-requests/analyze",
        json={"request_text": "Add an admin dashboard"},
    )
    assert r.status_code == 400
    assert "baseline" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_change_requests_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/change-requests")
    assert r.status_code == 200
    assert r.json() == []
