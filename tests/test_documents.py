"""Document upload, processing, query smoke tests.

Note: processing is async (Celery). We don't wait for READY status in
these tests — that would require polling and a running Celery worker.
Instead we test the upload endpoint and document CRUD, and separately
verify the query endpoint handles missing/unprocessed docs gracefully.
"""
import io
import pytest
from httpx import AsyncClient


# Minimal valid PDF bytes (1-page, 1x1pt white page).
# Generated offline — no external deps needed in tests.
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
async def test_upload_document(auth_client: AsyncClient):
    """Upload a PDF and get back an id + uploaded status."""
    r = await auth_client.post(
        "/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["status"] == "uploaded"

    doc_id = data["id"]

    # Verify it appears in the list
    r = await auth_client.get("/documents")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert doc_id in ids

    # Verify we can fetch it by id
    r = await auth_client.get(f"/documents/{doc_id}")
    assert r.status_code == 200
    doc = r.json()
    assert doc["id"] == doc_id
    assert doc["file_name"] == "test.pdf"


@pytest.mark.asyncio
async def test_upload_invalid_extension(auth_client: AsyncClient):
    """Uploading a non-PDF/DOCX file returns 400."""
    r = await auth_client.post(
        "/documents/upload",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert "invalid file type" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_empty_file(auth_client: AsyncClient):
    """Uploading an empty file returns 400."""
    r = await auth_client.post(
        "/documents/upload",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_nonexistent_document(auth_client: AsyncClient):
    """Fetching a document that doesn't exist returns 404."""
    r = await auth_client.get("/documents/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_document(auth_client: AsyncClient):
    """Upload then delete a document — it should be gone."""
    r = await auth_client.post(
        "/documents/upload",
        files={"file": ("delete_me.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    r = await auth_client.delete(f"/documents/{doc_id}")
    assert r.status_code == 200

    r = await auth_client.get(f"/documents/{doc_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_document_isolation(auth_client: AsyncClient, client: AsyncClient):
    """User A cannot access User B's documents."""
    import uuid

    # Upload as user A (auth_client)
    r = await auth_client.post(
        "/documents/upload",
        files={"file": ("secret.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    # Register + login as user B
    unique = uuid.uuid4().hex[:8]
    email_b = f"userb_{unique}@example.com"
    await client.post("/auth/register", json={
        "username": f"b_{unique}", "email": email_b, "password": "password123",
    })
    r = await client.post(
        "/auth/login",
        data={"username": email_b, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_b = r.json()["access_token"]

    # User B tries to fetch user A's document
    r = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code in (403, 404)

    # Cleanup user B
    await client.delete(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_b}"},
    )


@pytest.mark.asyncio
async def test_query_no_documents(auth_client: AsyncClient):
    """Querying with no documents returns a graceful no-content response."""
    r = await auth_client.post("/documents/query", json={
        "question": "What is this about?",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["has_answer"] is False