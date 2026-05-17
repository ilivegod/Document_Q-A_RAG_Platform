"""Shared test fixtures.

Tests run against the real running stack (api + postgres + redis).
Run with: docker compose exec api python -m pytest tests/ -v

Rate limits are flushed before each test to prevent inter-test interference.
"""
import pytest
import redis as _redis
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"


@pytest.fixture(autouse=True)
def flush_rate_limits():
    """Flush Redis before each test so rate limiters don't interfere."""
    try:
        _redis.Redis(host="redis", port=6379, db=0).flushdb()
    except Exception:
        pass


@pytest.fixture
async def client() -> AsyncClient:
    """Unauthenticated HTTP client pointing at the running API."""
    async with AsyncClient(base_url=BASE_URL) as c:
        yield c


@pytest.fixture
async def auth_client(client: AsyncClient):
    """Authenticated client — registers + logs in a fresh user per test."""
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