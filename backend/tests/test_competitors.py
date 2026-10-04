import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_competitor_crud(client: AsyncClient):
    # Setup user & org & workspace
    await client.post(
        "/api/v1/auth/register",
        json={"email": "compuser@example.com", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "compuser@example.com", "password": "Password123!"},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    org_res = await client.get("/api/v1/organizations/", headers=headers)
    org_id = org_res.json()[0]["id"]

    ws_list = await client.get(
        f"/api/v1/organizations/{org_id}/workspaces",
        headers=headers,
    )
    ws_id = ws_list.json()[0]["id"]

    # Create Competitor
    comp_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors",
        json={
            "name": "Stripe",
            "description": "Payment platform competitor",
            "website_url": "https://stripe.com",
            "initial_urls": [
                {
                    "url": "https://stripe.com/pricing",
                    "url_type": "pricing",
                    "scrape_interval_minutes": 120,
                }
            ],
        },
        headers=headers,
    )
    assert comp_res.status_code == 201, comp_res.text
    comp = comp_res.json()
    assert comp["name"] == "Stripe"
    assert len(comp["urls"]) == 1
    assert comp["urls"][0]["url"] == "https://stripe.com/pricing"

    # List Competitors
    list_res = await client.get(
        f"/api/v1/workspaces/{ws_id}/competitors",
        headers=headers,
    )
    assert list_res.status_code == 200
    paginated = list_res.json()
    assert paginated["total"] == 1
    assert paginated["items"][0]["name"] == "Stripe"
