import pytest
from httpx import AsyncClient

from app.api.v1.auth import REFRESH_COOKIE
from app.core.config import settings


@pytest.fixture(autouse=True)
def _plain_http_cookies(monkeypatch):
    # The test client talks plain http to "test", where a Secure cookie
    # would never be sent back.
    monkeypatch.setattr(settings, "REFRESH_COOKIE_SECURE", False)


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # 1. Register
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "Password123!",
            "full_name": "Test User",
        },
    )
    assert reg_response.status_code == 201, reg_response.text
    data = reg_response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"

    # 2. Login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "Password123!",
        },
    )
    assert login_response.status_code == 200, login_response.text
    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" not in tokens

    set_cookie = login_response.headers["set-cookie"]
    assert set_cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=strict" in set_cookie

    # 3. Get /me
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200, me_response.text
    user_info = me_response.json()
    assert user_info["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_duplicate_registration_fails(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "Password123!",
        },
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


async def _login(client: AsyncClient, email: str) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_refresh_rotates_cookie_and_rejects_reuse(client: AsyncClient):
    await _login(client, "rotate@example.com")
    old_cookie = client.cookies[REFRESH_COOKIE]

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200, response.text
    assert "access_token" in response.json()
    new_cookie = client.cookies[REFRESH_COOKIE]
    assert new_cookie != old_cookie

    # The old token was single-use.
    client.cookies.clear()
    reuse = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{REFRESH_COOKIE}={old_cookie}"},
    )
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie_fails(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing refresh token"


@pytest.mark.asyncio
async def test_logout_revokes_and_clears_cookie(client: AsyncClient):
    await _login(client, "logout@example.com")
    token = client.cookies[REFRESH_COOKIE]

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert REFRESH_COOKIE not in client.cookies

    reuse = await client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{REFRESH_COOKIE}={token}"},
    )
    assert reuse.status_code == 401
