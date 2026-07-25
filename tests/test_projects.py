"""Project workspace CRUD and isolation tests."""
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


@pytest.mark.asyncio
async def test_create_and_list_projects(auth_client: AsyncClient):
    r = await auth_client.post(
        "/projects",
        json={"name": "Indie SaaS MVP", "project_type": "indie"},
    )
    assert r.status_code == 201
    project = r.json()
    assert project["name"] == "Indie SaaS MVP"
    assert project["project_type"] == "indie"
    assert project["document_count"] == 0

    r = await auth_client.get("/projects")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "Indie SaaS MVP" in names


@pytest.mark.asyncio
async def test_get_update_delete_project(auth_client: AsyncClient):
    r = await auth_client.post(
        "/projects",
        json={"name": "Client EHR", "project_type": "client", "client_name": "Acme"},
    )
    project_id = r.json()["id"]

    r = await auth_client.get(f"/projects/{project_id}")
    assert r.status_code == 200
    assert r.json()["client_name"] == "Acme"

    r = await auth_client.patch(
        f"/projects/{project_id}",
        json={"name": "Client EHR v2"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Client EHR v2"

    r = await auth_client.delete(f"/projects/{project_id}")
    assert r.status_code == 204

    r = await auth_client.get(f"/projects/{project_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_project_document_upload(auth_client: AsyncClient):
    r = await auth_client.post(
        "/projects",
        json={"name": "Upload Test", "project_type": "indie"},
    )
    project_id = r.json()["id"]

    r = await auth_client.post(
        f"/projects/{project_id}/documents/upload",
        files={"file": ("brief.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    r = await auth_client.get(f"/projects/{project_id}/documents")
    assert r.status_code == 200
    assert any(d["id"] == doc_id for d in r.json())

    r = await auth_client.get(f"/projects/{project_id}/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["project_id"] == project_id


@pytest.mark.asyncio
async def test_project_isolation(auth_client: AsyncClient, client: AsyncClient):
    r = await auth_client.post(
        "/projects",
        json={"name": "Private Project", "project_type": "indie"},
    )
    project_id = r.json()["id"]

    # User B cannot access it
    unique = uuid.uuid4().hex[:8]
    email = f"other_{unique}@example.com"
    await client.post(
        "/auth/register",
        json={
            "username": f"other_{unique}",
            "email": email,
            "password": "testpassword123",
        },
    )
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    r = await client.get(f"/projects/{project_id}")
    assert r.status_code == 404

    try:
        await client.delete("/auth/me")
    except Exception:
        pass
