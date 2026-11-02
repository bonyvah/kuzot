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


async def _setup_competitor(client: AsyncClient, email: str) -> tuple[str, str, dict]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org_id = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]["id"]
    ws_id = (
        await client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers)
    ).json()[0]["id"]
    comp = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors", json={"name": "Acme"}, headers=headers
    )
    return ws_id, comp.json()["id"], headers


@pytest.mark.asyncio
async def test_duplicate_url_returns_conflict(client: AsyncClient):
    ws_id, comp_id, headers = await _setup_competitor(client, "dupurl@example.com")
    url = {"url": "https://acme.example/dup-pricing", "url_type": "pricing"}

    first = await client.post(f"/api/v1/competitors/{comp_id}/urls", json=url, headers=headers)
    assert first.status_code == 201, first.text

    again = await client.post(f"/api/v1/competitors/{comp_id}/urls", json=url, headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "This URL is already being monitored"

    new_comp = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors",
        json={"name": "Copycat", "initial_urls": [url]},
        headers=headers,
    )
    assert new_comp.status_code == 409


@pytest.mark.asyncio
async def test_url_list_cache_tracks_add_and_delete(client: AsyncClient):
    _, comp_id, headers = await _setup_competitor(client, "urlcache@example.com")
    list_path = f"/api/v1/competitors/{comp_id}/urls"

    # Prime the cache with the empty list.
    assert (await client.get(list_path, headers=headers)).json() == []

    added = await client.post(
        list_path, json={"url": "https://acme.example/cache-blog", "url_type": "blog"}, headers=headers
    )
    assert added.status_code == 201, added.text
    urls = (await client.get(list_path, headers=headers)).json()
    assert [u["id"] for u in urls] == [added.json()["id"]]

    deleted = await client.delete(f"/api/v1/monitored-urls/{added.json()['id']}", headers=headers)
    assert deleted.status_code == 200
    assert (await client.get(list_path, headers=headers)).json() == []
