import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_organization_crud(client: AsyncClient):
    # Register user
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"email": "orguser@example.com", "password": "Password123!"},
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "orguser@example.com", "password": "Password123!"},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # List orgs (should have automatic personal org)
    list_res = await client.get("/api/v1/organizations/", headers=headers)
    assert list_res.status_code == 200
    orgs = list_res.json()
    assert len(orgs) == 1

    # Create new org
    create_res = await client.post(
        "/api/v1/organizations/",
        json={"name": "Acme Corp", "org_type": "team"},
        headers=headers,
    )
    assert create_res.status_code == 201
    new_org = create_res.json()
    assert new_org["name"] == "Acme Corp"

    # Update org
    update_res = await client.put(
        f"/api/v1/organizations/{new_org['id']}",
        json={"name": "Acme Global"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Acme Global"

    # Attempt to create 2nd personal org (should fail with 400)
    personal_res = await client.post(
        "/api/v1/organizations/",
        json={"name": "Second Personal Org", "org_type": "personal"},
        headers=headers,
    )
    assert personal_res.status_code == 400
    assert "Maximum 1 personal organization allowed" in personal_res.json()["detail"]

    # Attempt to add member to personal org (should fail with 400)
    personal_org_id = orgs[0]["id"]
    invite_res = await client.post(
        f"/api/v1/organizations/{personal_org_id}/members",
        json={"user_id": reg_res.json()["id"], "role": "member"},
        headers=headers,
    )
    assert invite_res.status_code == 400
    assert "Personal organizations cannot have additional members" in invite_res.json()["detail"]
