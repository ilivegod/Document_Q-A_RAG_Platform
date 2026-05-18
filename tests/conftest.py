"""Shared test fixtures."""
import time
import httpx
import pytest
import redis as _redis
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"
_redis_client = _redis.Redis(host="redis", port=6379, db=0)


@pytest.fixture(scope="session", autouse=True)
def wait_for_server():
    """Wait for the API server to be ready."""
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
def flush_rate_limits():
    """Flush Redis before each test."""
    _redis_client.flushdb()


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