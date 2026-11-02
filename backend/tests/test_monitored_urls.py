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
async def test_trigger_is_rejected_while_a_scrape_is_in_flight(
    client: AsyncClient, enqueued
):
    url_id, headers = await _create_url(client, "twice@example.com")

    first = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)
    second = await client.post(f"/api/v1/monitored-urls/{url_id}/trigger", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already being scraped" in second.json()["detail"]
    assert enqueued == [first.json()["id"]]  # no second job, nothing re-sent


@pytest.mark.asyncio
async def test_finished_job_does_not_block_next_trigger(
    client: AsyncClient, monkeypatch
):
    url_id, headers = await _create_url(client, "again@example.com")
    trigger_url = f"/api/v1/monitored-urls/{url_id}/trigger"

    def broken(job_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(monitored_urls_api, "enqueue_scrape", broken)
    failed = await client.post(trigger_url, headers=headers)
    monkeypatch.setattr(monitored_urls_api, "enqueue_scrape", lambda job_id: None)
    retry = await client.post(trigger_url, headers=headers)

    assert failed.status_code == 503  # job marked FAILED: finished, not in flight
    assert retry.status_code == 201


@pytest.mark.asyncio
async def test_page_types_labels_and_intervals(client: AsyncClient):
    url_id, headers = await _create_url(client, "types@example.com")
    me = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{me['id']}/workspaces", headers=headers)).json()[0]
    comp = (await client.get(f"/api/v1/workspaces/{ws['id']}/competitors", headers=headers)).json()["items"][0]
    add = f"/api/v1/competitors/{comp['id']}/urls"

    # Daily by default, social types accepted
    res = await client.post(add, json={"url": "https://t.me/s/acme_news", "url_type": "telegram"}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["scrape_interval_minutes"] == 1440
    assert res.json()["label"] is None

    # "other" needs a label; other types drop one
    no_label = await client.post(add, json={"url": "https://linkedin.com/company/acme", "url_type": "other"}, headers=headers)
    assert no_label.status_code == 422
    other = await client.post(
        add, json={"url": "https://linkedin.com/company/acme", "url_type": "other", "label": " LinkedIn "}, headers=headers
    )
    assert other.json()["label"] == "LinkedIn"
    dropped = await client.post(add, json={"url": "https://x.com/acme", "url_type": "x", "label": "ignored"}, headers=headers)
    assert dropped.json()["label"] is None

    # Any interval between 15 minutes and 30 days
    for minutes, code in [(14, 422), (4320, 201), (43201, 422)]:
        res = await client.post(
            add, json={"url": f"https://acme.example/i{minutes}", "scrape_interval_minutes": minutes}, headers=headers
        )
        assert res.status_code == code, (minutes, res.text)

    # PATCH takes a JSON body and only changes what is sent
    patch = f"/api/v1/monitored-urls/{other.json()['id']}"
    res = await client.patch(patch, json={"scrape_interval_minutes": 4320}, headers=headers)
    assert res.json()["scrape_interval_minutes"] == 4320 and res.json()["label"] == "LinkedIn"
    res = await client.patch(patch, json={"scrape_interval_minutes": None}, headers=headers)
    assert res.json()["scrape_interval_minutes"] is None  # manual only
    res = await client.patch(patch, json={"url_type": "blog"}, headers=headers)
    assert res.json()["url_type"] == "blog" and res.json()["label"] is None
    res = await client.patch(patch, json={"url_type": "other"}, headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_competitor_history_spans_its_pages(client: AsyncClient, enqueued):
    url_id, headers = await _create_url(client, "history@example.com")
    org = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=headers)).json()[0]
    comp = (await client.get(f"/api/v1/workspaces/{ws['id']}/competitors", headers=headers)).json()["items"][0]
    other = await client.post(
        f"/api/v1/competitors/{comp['id']}/urls", json={"url": "https://acme.com/history-blog", "url_type": "blog"}, headers=headers
    )
    for uid in (url_id, other.json()["id"], url_id):
        assert (await client.post(f"/api/v1/monitored-urls/{uid}/trigger", headers=headers)).status_code in (201, 409)

    history = f"/api/v1/competitors/{comp['id']}/jobs"
    all_jobs = (await client.get(history, headers=headers)).json()
    assert {j["monitored_url_id"] for j in all_jobs["items"]} == {url_id, other.json()["id"]}
    one = (await client.get(history, params={"url_id": other.json()["id"]}, headers=headers)).json()
    assert one["total"] == 1

    stranger = await client.post("/api/v1/auth/register", json={"email": "history-x@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "history-x@example.com", "password": "Password123!"})
    denied = await client.get(history, headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert stranger.status_code == 201 and denied.status_code == 403
