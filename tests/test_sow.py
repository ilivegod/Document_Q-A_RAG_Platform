"""SOW and public portal API tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sow_crud_and_public_accept(auth_client: AsyncClient):
    r = await auth_client.post(
        "/projects",
        json={
            "name": "Portal Client",
            "project_type": "client",
            "client_name": "Acme Corp",
        },
    )
    project_id = r.json()["id"]

    r = await auth_client.get(f"/projects/{project_id}/sow")
    assert r.status_code == 200
    sow = r.json()
    assert sow["status"] == "draft"

    tiers = [
        {
            "tier_key": "mvp",
            "tier_name": "MVP",
            "description": "Core launch",
            "total_hours": 80,
            "total_cost": 8000,
            "requirement_ids": [],
            "estimated_weeks": 4,
            "contingency_applied": False,
        },
        {
            "tier_key": "recommended",
            "tier_name": "Recommended",
            "description": "Balanced scope",
            "total_hours": 120,
            "total_cost": 12000,
            "requirement_ids": [],
            "estimated_weeks": 6,
            "contingency_applied": False,
        },
    ]
    r = await auth_client.patch(
        f"/projects/{project_id}/sow",
        json={"tiers": tiers, "hourly_rate": 100, "deposit_percentage": 30},
    )
    assert r.status_code == 200
    assert len(r.json()["tiers"]) == 2

    r = await auth_client.post(f"/projects/{project_id}/sow/send")
    assert r.status_code == 200
    assert r.json()["status"] == "sent"

    r = await auth_client.post(f"/projects/{project_id}/sow/portal-link")
    assert r.status_code == 200
    portal = r.json()
    token = portal["token"]
    assert "/p/" in portal["portal_url"]

    from httpx import AsyncClient as PlainClient

    async with PlainClient(base_url=auth_client.base_url) as public_client:
        r = await public_client.get(f"/public/portal/{token}")
        assert r.status_code == 200
        assert r.json()["project_name"] == "Portal Client"

        r = await public_client.get(f"/public/portal/{token}/sow")
        assert r.status_code == 200
        assert len(r.json()["tiers"]) == 2

        r = await public_client.post(
            f"/public/portal/{token}/sow/accept",
            json={"tier_key": "recommended"},
        )
        assert r.status_code == 200
        assert r.json()["accepted_tier_key"] == "recommended"

    r = await auth_client.get(f"/projects/{project_id}/sow")
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    assert r.json()["accepted_tier_key"] == "recommended"
