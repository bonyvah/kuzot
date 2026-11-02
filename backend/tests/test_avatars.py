import pytest
from httpx import AsyncClient

from app.core import storage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture
def bucket(monkeypatch) -> dict[str, tuple[bytes, str]]:
    stored: dict[str, tuple[bytes, str]] = {}
    monkeypatch.setattr(storage, "put_object", lambda key, data, ct: stored.__setitem__(key, (data, ct)))
    monkeypatch.setattr(storage, "delete_object", lambda key: stored.pop(key))
    return stored


async def _setup(client: AsyncClient, email: str) -> tuple[dict, dict, dict]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=headers)).json()[0]
    return headers, org, ws


@pytest.mark.asyncio
async def test_org_emoji_and_image(client: AsyncClient, bucket):
    headers, org, _ = await _setup(client, "avatar-org@example.com")
    base = f"/api/v1/organizations/{org['id']}/avatar"
    assert org["avatar_emoji"] is None and org["avatar_url"] is None

    res = await client.put(base, json={"emoji": "🚲"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["avatar_emoji"] == "🚲"

    for bad in ["", "ab", "🚲 🚲", "x" * 40]:
        assert (await client.put(base, json={"emoji": bad}, headers=headers)).status_code == 422

    # An image replaces the emoji and is served from MEDIA_BASE_URL
    res = await client.post(f"{base}/image", files={"file": ("logo.png", PNG, "image/png")}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["avatar_emoji"] is None
    assert body["avatar_url"].startswith(f"/media/avatars/orgs/{org['id']}/")
    key = body["avatar_url"].removeprefix("/media/")
    assert bucket[key] == (PNG, "image/png")

    # Back to an emoji: the stored image is deleted
    res = await client.put(base, json={"emoji": "👨‍👩‍👧"}, headers=headers)
    assert res.json()["avatar_url"] is None
    assert bucket == {}

    res = await client.delete(base, headers=headers)
    assert res.json()["avatar_emoji"] is None


@pytest.mark.asyncio
async def test_image_upload_is_checked(client: AsyncClient, bucket):
    headers, org, _ = await _setup(client, "avatar-check@example.com")
    url = f"/api/v1/organizations/{org['id']}/avatar/image"

    # The file's bytes decide, not the claimed content type
    svg = await client.post(url, files={"file": ("x.png", SVG, "image/png")}, headers=headers)
    assert svg.status_code == 415
    big = await client.post(url, files={"file": ("big.png", PNG + b"\x00" * (2 * 1024 * 1024), "image/png")}, headers=headers)
    assert big.status_code == 413
    assert bucket == {}


@pytest.mark.asyncio
async def test_workspace_avatar_and_permissions(client: AsyncClient, bucket):
    headers, _, ws = await _setup(client, "avatar-ws@example.com")
    res = await client.post(
        f"/api/v1/workspaces/{ws['id']}/avatar/image", files={"file": ("w.png", PNG, "image/png")}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["avatar_url"].startswith(f"/media/avatars/workspaces/{ws['id']}/")
    listed = (await client.get(f"/api/v1/organizations/{ws['org_id']}/workspaces", headers=headers)).json()
    assert listed[0]["avatar_url"] == res.json()["avatar_url"]

    # Deleting the workspace removes its image
    assert (await client.delete(f"/api/v1/workspaces/{ws['id']}", headers=headers)).status_code == 200
    assert bucket == {}

    # Members of a team can't change its avatar; admins can
    owner, _, _ = await _setup(client, "avatar-owner@example.com")
    team = (await client.post("/api/v1/organizations/", json={"name": "Avatars", "org_type": "team"}, headers=owner)).json()
    await client.post(f"/api/v1/organizations/{team['id']}/members", json={"email": "avatar-ws@example.com"}, headers=owner)
    denied = await client.put(f"/api/v1/organizations/{team['id']}/avatar", json={"emoji": "🔥"}, headers=headers)
    assert denied.status_code == 403
