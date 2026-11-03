from httpx import AsyncClient

from app.insights import started
from app.schemas.insight import InsightPublic


class FakeInsights:
    def __init__(self):
        self.docs: list[dict] = []

    async def insert_many(self, docs, ordered=True):
        self.docs += docs


class FakeMongo:
    def __init__(self):
        self.insights = FakeInsights()


def test_started_headline():
    assert started.started_headline("pricing", None) == "Now monitoring their pricing page"
    assert started.started_headline("x", None) == "Now monitoring their X account"
    assert started.started_headline("other", "LinkedIn") == "Now monitoring their LinkedIn"


async def test_new_pages_get_a_monitoring_started_insight(client: AsyncClient, monkeypatch):
    mongo = FakeMongo()
    monkeypatch.setattr(started, "get_mongo_db", lambda: mongo)
    await client.post("/api/v1/auth/register", json={"email": "started@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "started@example.com", "password": "Password123!"})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = (await client.get("/api/v1/organizations/", headers=h)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=h)).json()[0]

    comp = await client.post(
        f"/api/v1/workspaces/{ws['id']}/competitors",
        json={"name": "Startco", "initial_urls": [{"url": "https://startco.io/pricing", "url_type": "pricing"}]},
        headers=h,
    )
    assert comp.status_code == 201, comp.text
    res = await client.post(
        f"/api/v1/competitors/{comp.json()['id']}/urls",
        json={"url": "https://t.me/startco", "url_type": "telegram"},
        headers=h,
    )
    assert res.status_code == 201, res.text

    assert [d["headline"] for d in mongo.insights.docs] == [
        "Now monitoring their pricing page",
        "Now monitoring their Telegram channel",
    ]
    doc = mongo.insights.docs[1]
    assert doc["kind"] == "monitoring_started" and doc["workspace_id"] == ws["id"]
    # the feed can serve it
    InsightPublic(**doc, id="x", workspace_name="W", competitor_name="Startco")


async def test_mongo_failure_does_not_block_adding(client: AsyncClient, monkeypatch):
    def broken():
        raise RuntimeError("MongoDB not connected")

    monkeypatch.setattr(started, "get_mongo_db", broken)
    await client.post("/api/v1/auth/register", json={"email": "started2@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "started2@example.com", "password": "Password123!"})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = (await client.get("/api/v1/organizations/", headers=h)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=h)).json()[0]
    comp = await client.post(
        f"/api/v1/workspaces/{ws['id']}/competitors",
        json={"name": "Startco2", "initial_urls": [{"url": "https://startco2.io"}]},
        headers=h,
    )
    assert comp.status_code == 201, comp.text
