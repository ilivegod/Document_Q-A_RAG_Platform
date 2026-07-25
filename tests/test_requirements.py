"""Requirements and baseline API tests."""
import io
import uuid

import pytest
from httpx import AsyncClient

MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 1 1]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n190\n%%EOF"
)


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


@pytest.mark.asyncio
async def test_approve_baseline_requires_confirmed(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/baselines/approve",
        json={},
    )
    assert r.status_code == 400
    assert "confirm" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_current_baseline_none(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/baselines/current")
    assert r.status_code == 200
    assert r.json() is None
