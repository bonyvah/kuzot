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


async def _login(client: AsyncClient, email: str) -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_team_members_by_email_and_owner_rules(client: AsyncClient):
    owner = await _login(client, "team-owner@example.com")
    admin = await _login(client, "team-admin@example.com")
    member = await _login(client, "team-member@example.com")

    org = (
        await client.post("/api/v1/organizations/", json={"name": "Team Rules", "org_type": "team"}, headers=owner)
    ).json()
    members_path = f"/api/v1/organizations/{org['id']}/members"

    # Add by email, case-insensitively; the response says who was added
    added = await client.post(members_path, json={"email": "Team-Admin@Example.com", "role": "admin"}, headers=owner)
    assert added.status_code == 201, added.text
    assert added.json()["email"] == "team-admin@example.com"
    admin_id = added.json()["user_id"]

    unknown = await client.post(members_path, json={"email": "nobody@example.com"}, headers=owner)
    assert unknown.status_code == 404

    neither = await client.post(members_path, json={"role": "member"}, headers=owner)
    assert neither.status_code == 422

    # Admins can add members but can't grant ownership
    escalate = await client.post(members_path, json={"email": "team-member@example.com", "role": "owner"}, headers=admin)
    assert escalate.status_code == 403
    ok = await client.post(members_path, json={"email": "team-member@example.com"}, headers=admin)
    assert ok.status_code == 201
    member_id = ok.json()["user_id"]

    listed = (await client.get(members_path, headers=member)).json()
    assert [m["email"] for m in listed] == [
        "team-owner@example.com",
        "team-admin@example.com",
        "team-member@example.com",
    ]
    owner_id = listed[0]["user_id"]

    # The last owner can't be demoted, removed, or leave
    demote = await client.put(f"{members_path}/{owner_id}", json={"role": "admin"}, headers=owner)
    assert demote.status_code == 400
    leave_owner = await client.delete(f"{members_path}/{owner_id}", headers=owner)
    assert leave_owner.status_code == 400

    # Once there is a second owner, the first may step down
    promote = await client.put(f"{members_path}/{admin_id}", json={"role": "owner"}, headers=owner)
    assert promote.status_code == 200
    demote = await client.put(f"{members_path}/{owner_id}", json={"role": "member"}, headers=owner)
    assert demote.status_code == 200

    # Any member may leave; removing someone else takes an owner
    kick = await client.delete(f"{members_path}/{admin_id}", headers=member)
    assert kick.status_code == 403
    leave = await client.delete(f"{members_path}/{member_id}", headers=member)
    assert leave.status_code == 200


@pytest.mark.asyncio
async def test_personal_org_cannot_be_deleted(client: AsyncClient):
    headers = await _login(client, "keep-personal@example.com")
    personal = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]
    res = await client.delete(f"/api/v1/organizations/{personal['id']}", headers=headers)
    assert res.status_code == 400
