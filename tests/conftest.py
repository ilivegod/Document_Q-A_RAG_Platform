"""Shared test fixtures."""
import time
import httpx
import pytest
import redis as _redis
from httpx import AsyncClient

import os
_redis_host = os.getenv("REDIS_HOST", "redis")
_redis_client = _redis.Redis(host=_redis_host, port=6379, db=0)

BASE_URL = "http://localhost:8000"

_INTEGRATION_TEST_FILES = {
    "test_auth.py",
    "test_health.py",
    "test_documents.py",
    "test_closed_beta.py",
    "test_projects.py",
    "test_requirements.py",
    "test_technology.py",
    "test_sow.py",
}


def _needs_live_server(session) -> bool:
    return any(
        any(name in item.nodeid for name in _INTEGRATION_TEST_FILES)
        for item in session.items
    )


@pytest.fixture(scope="session", autouse=True)
def wait_for_server(request):
    """Wait for the API server when running integration tests."""
    if not _needs_live_server(request.session):
        return
    for _ in range(20):
        try:
            r = httpx.get(f"{BASE_URL}/health/live", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("API server did not start in time")


@pytest.fixture(autouse=True)
def flush_rate_limits(request):
    """Flush Redis before each integration test."""
    if not _needs_live_server(request.session):
        return
    try:
        _redis_client.flushdb()
    except Exception:
        pass


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(base_url=BASE_URL) as c:
        yield c


@pytest.fixture
async def auth_client(client: AsyncClient):
    import uuid
    unique = uuid.uuid4().hex[:8]
    email = f"test_{unique}@example.com"
    password = "testpassword123"

    r = await client.post("/auth/register", json={
        "username": f"test_{unique}",
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"Register failed: {r.text}"

    r = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    client._test_user = {"email": email, "password": password}

    yield client

    try:
        await client.delete("/auth/me")
    except Exception:
        pass