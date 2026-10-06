import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_monitored_url_and_scrape_jobs(client: AsyncClient):
    # 1. Register & setup workspace + competitor
    await client.post(
        "/api/v1/auth/register",
        json={"email": "monuser@example.com", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "monuser@example.com", "password": "Password123!"},
    )
    tokens = login_res.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    org_res = await client.get("/api/v1/organizations/", headers=headers)
    org_id = org_res.json()[0]["id"]

    ws_list = await client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers)
    ws_id = ws_list.json()[0]["id"]

    # 2. Create Competitor with initial URL
    comp_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors",
        json={
            "name": "Notion",
            "initial_urls": [{"url": "https://notion.so/pricing", "url_type": "pricing"}],
        },
        headers=headers,
    )
    comp_data = comp_res.json()
    url_id = comp_data["urls"][0]["id"]

    # 3. Trigger manual scrape job
    trigger_res = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)
    assert trigger_res.status_code == 201
    job_data = trigger_res.json()
    assert job_data["status"] == "pending"
    assert job_data["triggered_by"] == "manual"

    # 4. List job history for this URL
    jobs_res = await client.get(f"/api/v1/monitored-urls/{url_id}/jobs", headers=headers)
    assert jobs_res.status_code == 200
    assert jobs_res.json()["total"] == 1