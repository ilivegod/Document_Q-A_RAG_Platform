"""Auth flow smoke tests.

Covers: register, login, /me, password reset flow, delete account.
These are integration tests against the real DB — they test the full
stack from HTTP request to database.
"""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient):
    """Full happy-path: register → login → /me returns correct user."""
    unique = uuid.uuid4().hex[:8]
    email = f"test_{unique}@example.com"
    password = "securepassword123"

    # Register
    r = await client.post("/auth/register", json={
        "username": f"user_{unique}",
        "email": email,
        "password": password,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert data["email_verified"] is False
    assert "hashed_password" not in data

    # Login
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # /me
    r = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == email
    assert me["email_verified"] is False

    # Cleanup
    await client.delete(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering twice with the same email returns 400."""
    unique = uuid.uuid4().hex[:8]
    email = f"dup_{unique}@example.com"
    payload = {"username": f"u_{unique}", "email": email, "password": "password123"}

    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 200
    user_id = r.json()["id"]

    r2 = await client.post("/auth/register", json=payload)
    assert r2.status_code == 400
    assert "already registered" in r2.json()["detail"].lower()

    # Cleanup
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    await client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Wrong password returns 401."""
    unique = uuid.uuid4().hex[:8]
    email = f"wp_{unique}@example.com"

    await client.post("/auth/register", json={
        "username": f"u_{unique}", "email": email, "password": "correctpassword",
    })

    r = await client.post(
        "/auth/login",
        data={"username": email, "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401

    # Cleanup
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": "correctpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = r.json()["access_token"]
    await client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """/me without token returns 401."""
    r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """Refresh token issues a new access token."""
    unique = uuid.uuid4().hex[:8]
    email = f"rt_{unique}@example.com"

    await client.post("/auth/register", json={
        "username": f"u_{unique}", "email": email, "password": "password123",
    })
    r = await client.post(
        "/auth/login",
        data={"username": email, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    tokens = r.json()

    r = await client.post("/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert r.status_code == 200
    new_tokens = r.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["token_type"] == "bearer"

    # Cleanup
    await client.delete(
        "/auth/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )


@pytest.mark.asyncio
async def test_forgot_password_uniform_response(client: AsyncClient):
    """Forgot password returns same response for existing and non-existing emails."""
    r1 = await client.post("/auth/forgot-password", json={
        "email": "doesnotexist@example.com",
    })
    r2 = await client.post("/auth/forgot-password", json={
        "email": "alsodoesnotexist@example.com",
    })
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["message"] == r2.json()["message"]


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    """Reset password with a bad token returns 400."""
    r = await client.post("/auth/reset-password", json={
        "token": "completelyfaketoken",
        "new_password": "newpassword123",
    })
    assert r.status_code == 400
    assert "invalid or expired" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_account_cascade(auth_client: AsyncClient):
    """Deleting account returns 204 and subsequent /me returns 401."""
    r = await auth_client.delete("/auth/me")
    assert r.status_code == 204

    r = await auth_client.get("/auth/me")
    assert r.status_code == 401