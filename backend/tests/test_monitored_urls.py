import pytest
from httpx import AsyncClient

from app.api.v1 import monitored_urls as monitored_urls_api


@pytest.fixture
def enqueued(monkeypatch) -> list[str]:
    sent: list[str] = []
    monkeypatch.setattr(
        monitored_urls_api, "enqueue_scrape", lambda job_id: sent.append(str(job_id))
    )
    return sent


async def _create_url(client: AsyncClient, email: str) -> tuple[str, dict]:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org_id = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]["id"]
    ws_id = (
        await client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers)
    ).json()[0]["id"]
    comp = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors",
        json={
            "name": "Acme",
            "initial_urls": [{"url": f"https://acme.com/{email}", "url_type": "pricing"}],
        },
        headers=headers,
    )
    return comp.json()["urls"][0]["id"], headers


@pytest.mark.asyncio
async def test_monitored_url_and_scrape_jobs(client: AsyncClient, enqueued):
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
    assert enqueued == [job_data["id"]]

    # 4. List job history for this URL
    jobs_res = await client.get(f"/api/v1/monitored-urls/{url_id}/jobs", headers=headers)
    assert jobs_res.status_code == 200
    assert jobs_res.json()["total"] == 1


@pytest.mark.asyncio
async def test_trigger_returns_503_and_fails_job_when_broker_is_down(
    client: AsyncClient, monkeypatch
):
    def broken(job_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(monitored_urls_api, "enqueue_scrape", broken)
    url_id, headers = await _create_url(client, "brokerdown@example.com")

    res = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)

    assert res.status_code == 503
    jobs = (
        await client.get(f"/api/v1/monitored-urls/{url_id}/jobs", headers=headers)
    ).json()
    assert jobs["total"] == 1
    assert jobs["items"][0]["status"] == "failed"
    assert "enqueue" in jobs["items"][0]["error_message"]


@pytest.mark.asyncio
async def test_each_trigger_enqueues_its_own_job(client: AsyncClient, enqueued):
    url_id, headers = await _create_url(client, "twice@example.com")

    first = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)
    second = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)

    assert enqueued == [first.json()["id"], second.json()["id"]]
