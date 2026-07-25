"""Technology explorer API tests."""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(auth_client: AsyncClient) -> str:
    r = await auth_client.post(
        "/projects",
        json={"name": f"Tech test {uuid.uuid4().hex[:6]}", "project_type": "indie"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_explore_requires_project_context(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/technology/explore",
        json={"topic": "Best auth stack for this MVP?"},
    )
    assert r.status_code == 400
    assert "requirements" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_technology_explorations_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/technology")
    assert r.status_code == 200
    assert r.json() == []
