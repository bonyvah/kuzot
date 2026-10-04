import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_workspace_crud(client: AsyncClient):
    # Setup user & org
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wsuser@example.com", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "wsuser@example.com", "password": "Password123!"},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    org_res = await client.get("/api/v1/organizations/", headers=headers)
    org_id = org_res.json()[0]["id"]

    # Create workspace
    ws_create = await client.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Marketing Team", "description": "Competitor tracking workspace"},
        headers=headers,
    )
    assert ws_create.status_code == 201
    ws = ws_create.json()
    assert ws["name"] == "Marketing Team"

    # List workspaces
    ws_list = await client.get(
        f"/api/v1/organizations/{org_id}/workspaces",
        headers=headers,
    )
    assert ws_list.status_code == 200
    assert len(ws_list.json()) == 2  # General + Marketing Team
