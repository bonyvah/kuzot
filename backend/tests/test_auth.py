import pytest
from httpx import AsyncClient


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
    assert "refresh_token" in tokens

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
