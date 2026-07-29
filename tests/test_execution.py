"""Execution domain API tests."""
import uuid

import pytest
from httpx import AsyncClient


async def _create_project(auth_client: AsyncClient) -> str:
    r = await auth_client.post(
        "/projects",
        json={"name": f"Exec test {uuid.uuid4().hex[:6]}", "project_type": "indie"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
async def test_execution_board_empty(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)
    r = await auth_client.get(f"/projects/{project_id}/execution")
    assert r.status_code == 200
    data = r.json()
    assert data["milestones"] == []
    assert data["tasks"] == []
    assert data["decisions"] == []
    assert data["recent_activity"] == []
    assert data["pending_proposals"] == []
    assert data["task_counts"]["total"] == 0


@pytest.mark.asyncio
async def test_milestone_and_task_crud(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)

    m = await auth_client.post(
        f"/projects/{project_id}/milestones",
        json={"title": "MVP", "description": "Ship first version"},
    )
    assert m.status_code == 201
    milestone = m.json()
    assert milestone["title"] == "MVP"
    assert milestone["status"] == "planned"

    t = await auth_client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Set up auth",
            "milestone_id": milestone["id"],
            "status": "now",
            "priority": "must",
            "acceptance_criteria": ["Login works"],
        },
    )
    assert t.status_code == 201
    task = t.json()
    assert task["status"] == "now"
    assert task["milestone_id"] == milestone["id"]
    assert task["acceptance_criteria"] == ["Login works"]

    blocked = await auth_client.patch(
        f"/projects/{project_id}/tasks/{task['id']}",
        json={"status": "blocked"},
    )
    assert blocked.status_code == 400

    blocked = await auth_client.patch(
        f"/projects/{project_id}/tasks/{task['id']}",
        json={"status": "blocked", "blocker_reason": "Waiting on API keys"},
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["blocker_reason"] == "Waiting on API keys"

    board = await auth_client.get(f"/projects/{project_id}/execution")
    assert board.status_code == 200
    data = board.json()
    assert len(data["milestones"]) == 1
    assert len(data["tasks"]) == 1
    assert data["task_counts"]["blocked"] == 1
    assert len(data["recent_activity"]) >= 2


@pytest.mark.asyncio
async def test_decision_and_proposal_flow(auth_client: AsyncClient):
    project_id = await _create_project(auth_client)

    d = await auth_client.post(
        f"/projects/{project_id}/decisions",
        json={
            "title": "Use Postgres",
            "rationale": "Need relational + vector support",
        },
    )
    assert d.status_code == 201
    assert d.json()["status"] == "active"

    p = await auth_client.post(
        f"/projects/{project_id}/proposals",
        json={
            "proposal_type": "work_breakdown",
            "title": "Break down MVP",
            "summary": "Suggested tasks from requirements",
            "payload": {"tasks": [{"title": "Auth"}]},
        },
    )
    assert p.status_code == 201
    proposal = p.json()
    assert proposal["status"] == "pending"

    decided = await auth_client.patch(
        f"/projects/{project_id}/proposals/{proposal['id']}",
        json={"status": "approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert decided.json()["decided_at"] is not None

    note = await auth_client.post(
        f"/projects/{project_id}/activity",
        json={"summary": "Checked in after approving the plan", "event_type": "note"},
    )
    assert note.status_code == 201
    assert note.json()["summary"].startswith("Checked in")
