"""Technology stack API tests."""
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
async def test_list_technology_stack_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/technology")
    assert r.status_code == 200
    assert r.json()["categories"] == {}
    assert r.json()["category_descriptions"] == {}


@pytest.mark.asyncio
async def test_generate_requires_requirements(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(f"/projects/{project_id}/technology/generate")
    assert r.status_code == 400
    assert "requirements" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_search_catalog(auth_client: AsyncClient):
    r = await auth_client.get("/technology/catalog", params={"query": "next"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0
    assert any(item["id"] == "nextjs" for item in data)
    nextjs = next(item for item in data if item["id"] == "nextjs")
    assert nextjs["summary"]
    assert nextjs["usage_hint"]


@pytest.mark.asyncio
async def test_add_unknown_catalog_item_rejected(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/technology",
        json={"catalog_id": "not-a-real-tech"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_add_and_remove_catalog_item(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/technology",
        json={"catalog_id": "nextjs"},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["catalog_id"] == "nextjs"
    assert item["name"] == "Next.js"
    assert item["summary"]
    assert item["usage_hint"]

    dup = await auth_client.post(
        f"/projects/{project_id}/technology",
        json={"catalog_id": "nextjs"},
    )
    assert dup.status_code == 409

    stack = await auth_client.get(f"/projects/{project_id}/technology")
    assert stack.status_code == 200
    assert "frontend" in stack.json()["categories"]
    assert "frontend" in stack.json()["category_descriptions"]

    deleted = await auth_client.delete(
        f"/projects/{project_id}/technology/{item['id']}"
    )
    assert deleted.status_code == 204

    stack_after = await auth_client.get(f"/projects/{project_id}/technology")
    assert stack_after.json()["categories"] == {}
