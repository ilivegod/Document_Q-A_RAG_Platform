"""Decision log API tests."""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(auth_client: AsyncClient) -> str:
    r = await auth_client.post(
        "/projects",
        json={"name": f"Decision test {uuid.uuid4().hex[:6]}", "project_type": "indie"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_list_decisions_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/decisions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_and_accept_decision(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/decisions",
        json={
            "title": "Use PostgreSQL for persistence",
            "category": "technology",
            "chosen_option": "PostgreSQL + pgvector",
            "rationale": "Already used in the stack for RAG embeddings.",
            "alternatives_considered": ["MongoDB", "SQLite"],
        },
    )
    assert r.status_code == 201
    decision = r.json()
    assert decision["status"] == "proposed"
    assert decision["chosen_option"] == "PostgreSQL + pgvector"

    r = await auth_client.post(
        f"/projects/{project_id}/decisions/{decision['id']}/accept"
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_from_exploration_not_found(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.post(
        f"/projects/{project_id}/decisions/from-exploration/{uuid.uuid4()}"
    )
    assert r.status_code == 404
