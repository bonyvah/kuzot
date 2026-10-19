from datetime import datetime

import openai
import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.api.v1 import intelligence
from app.db.dependencies import get_mongodb
from app.main import app
from app.rag.reports import GeneratedReport
from app.rag.search import Hit


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        self.docs = sorted(self.docs, key=lambda d: d[key], reverse=direction < 0)
        return self

    def skip(self, n):
        self.docs = self.docs[n:]
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __aiter__(self):
        self._it = iter(self.docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class FakeReports:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        doc["_id"] = ObjectId()
        self.docs.append(dict(doc))
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query):
        return next((d for d in self.docs if d["_id"] == query["_id"]), None)

    async def count_documents(self, query):
        return len(self._match(query))

    def find(self, query, projection=None):
        return FakeCursor(self._match(query))

    def _match(self, query):
        return [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]


@pytest.fixture
def mongo():
    fake = type("Mongo", (), {"reports": FakeReports()})()
    app.dependency_overrides[get_mongodb] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mongodb, None)


@pytest.fixture
def searches(monkeypatch):
    """Record search calls; tests set `.hits` to what Pinecone should return."""

    class Recorder:
        hits: list[Hit] = []
        calls: list[tuple] = []

    def fake_search(query, org_id, filters, top_k):
        Recorder.calls.append((query, org_id, filters, top_k))
        return Recorder.hits

    Recorder.calls = []
    monkeypatch.setattr(intelligence, "search", fake_search)
    return Recorder


@pytest.fixture
def generated(monkeypatch):
    def fake_generate(prompt, hits, names):
        return GeneratedReport(
            content="Acme raised prices [1].", cited={1}, model="gpt-test"
        )

    monkeypatch.setattr(intelligence, "generate_report", fake_generate)


async def _setup(client: AsyncClient, email: str) -> dict:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org_id = (await client.get("/api/v1/organizations/", headers=headers)).json()[0][
        "id"
    ]
    ws_id = (
        await client.get(f"/api/v1/organizations/{org_id}/workspaces", headers=headers)
    ).json()[0]["id"]
    comp = await client.post(
        f"/api/v1/workspaces/{ws_id}/competitors",
        json={"name": "Acme", "initial_urls": [{"url": f"https://acme.com/{email}"}]},
        headers=headers,
    )
    return {
        "headers": headers,
        "org_id": org_id,
        "ws_id": ws_id,
        "competitor_id": comp.json()["id"],
        "url_id": comp.json()["urls"][0]["id"],
    }


def _hit(ctx: dict, text: str, removed_at: datetime | None = None) -> Hit:
    return Hit(
        chunk_id=f"{ctx['url_id']}#{len(text)}",
        score=0.8,
        text=text,
        competitor_id=ctx["competitor_id"],
        monitored_url_id=ctx["url_id"],
        url="https://acme.com/pricing",
        url_type="pricing",
        snapshot_id="s1",
        first_seen_at=datetime(2026, 10, 1),
        removed_at=removed_at,
    )


async def test_search_returns_hits_scoped_to_workspace(client: AsyncClient, searches):
    ctx = await _setup(client, "search1@example.com")
    searches.hits = [_hit(ctx, "Pro plan is $20")]

    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/search",
        json={"query": "pricing", "url_types": ["pricing"], "top_k": 3},
        headers=ctx["headers"],
    )

    assert res.status_code == 200
    hit = res.json()["hits"][0]
    assert hit["competitor_name"] == "Acme"
    assert hit["is_current"] is True
    query, org_id, filters, top_k = searches.calls[0]
    assert org_id == ctx["org_id"]
    assert filters.workspace_id == ctx["ws_id"]
    assert filters.current_only is True  # default scope
    assert filters.url_types == ["pricing"]
    assert top_k == 3


async def test_search_scope_all_includes_history(client: AsyncClient, searches):
    ctx = await _setup(client, "search2@example.com")
    searches.hits = []

    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/search",
        json={"query": "pricing", "scope": "all"},
        headers=ctx["headers"],
    )

    assert res.status_code == 200
    assert searches.calls[0][2].current_only is False


async def test_search_rejects_non_members(client: AsyncClient, searches):
    owner = await _setup(client, "search3@example.com")
    outsider = await _setup(client, "search4@example.com")

    res = await client.post(
        f"/api/v1/workspaces/{owner['ws_id']}/search",
        json={"query": "pricing"},
        headers=outsider["headers"],
    )

    assert res.status_code == 403
    assert searches.calls == []


async def test_search_maps_ai_outage_to_503(client: AsyncClient, monkeypatch):
    ctx = await _setup(client, "search5@example.com")

    def down(*args):
        raise openai.APIConnectionError(request=None)  # type: ignore[arg-type]

    monkeypatch.setattr(intelligence, "search", down)
    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/search",
        json={"query": "pricing"},
        headers=ctx["headers"],
    )
    assert res.status_code == 503


async def test_report_is_generated_stored_and_listed(
    client: AsyncClient, searches, generated, mongo
):
    ctx = await _setup(client, "report1@example.com")
    searches.hits = [
        _hit(ctx, "Pro plan is $25"),
        _hit(ctx, "Pro plan is $20", removed_at=datetime(2026, 10, 3)),
    ]

    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/reports",
        json={"prompt": "Did Acme change pricing?"},
        headers=ctx["headers"],
    )

    assert res.status_code == 201
    report = res.json()
    assert report["content"] == "Acme raised prices [1]."
    assert [(s["number"], s["cited"]) for s in report["sources"]] == [
        (1, True),
        (2, False),
    ]
    assert report["sources"][1]["is_current"] is False
    assert searches.calls[0][2].current_only is False  # reports see history

    listed = await client.get(
        f"/api/v1/workspaces/{ctx['ws_id']}/reports", headers=ctx["headers"]
    )
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == report["id"]

    fetched = await client.get(
        f"/api/v1/reports/{report['id']}", headers=ctx["headers"]
    )
    assert fetched.status_code == 200
    assert fetched.json()["sources"] == report["sources"]


async def test_report_without_matching_content_is_404(
    client: AsyncClient, searches, generated, mongo
):
    ctx = await _setup(client, "report2@example.com")
    searches.hits = []

    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/reports",
        json={"prompt": "Anything new?"},
        headers=ctx["headers"],
    )

    assert res.status_code == 404
    assert mongo.reports.docs == []


async def test_report_is_private_to_its_org(
    client: AsyncClient, searches, generated, mongo
):
    owner = await _setup(client, "report3@example.com")
    outsider = await _setup(client, "report4@example.com")
    searches.hits = [_hit(owner, "Pro plan is $25")]
    created = await client.post(
        f"/api/v1/workspaces/{owner['ws_id']}/reports",
        json={"prompt": "Pricing?"},
        headers=owner["headers"],
    )

    res = await client.get(
        f"/api/v1/reports/{created.json()['id']}", headers=outsider["headers"]
    )

    assert res.status_code == 403


async def test_unknown_report_id_is_404(client: AsyncClient, mongo):
    ctx = await _setup(client, "report5@example.com")
    for report_id in ("not-an-id", str(ObjectId())):
        res = await client.get(f"/api/v1/reports/{report_id}", headers=ctx["headers"])
        assert res.status_code == 404
