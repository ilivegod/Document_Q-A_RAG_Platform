"""Requirements API tests."""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(auth_client: AsyncClient) -> str:
    r = await auth_client.post(
        "/projects",
        json={"name": f"Req test {uuid.uuid4().hex[:6]}", "project_type": "indie"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_list_requirements_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/requirements")
    assert r.status_code == 200
    data = r.json()
    assert data["requirements"] == []
    assert data["open_questions"] == []


@pytest.mark.asyncio
async def test_extract_requires_ready_documents(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(f"/projects/{project_id}/requirements/extract")
    assert r.status_code == 400
    assert "at least one document" in r.json()["detail"].lower()
