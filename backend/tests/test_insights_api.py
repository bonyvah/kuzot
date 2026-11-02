from datetime import datetime, timedelta

import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.db.dependencies import get_mongodb
from app.insights import headline
from app.insights.builder import build_insight
from app.main import app


def _match(doc: dict, query: dict) -> bool:
    for key, cond in query.items():
        if key == "$or":
            if not any(_match(doc, sub) for sub in cond):
                return False
        elif isinstance(cond, dict):
            value = doc.get(key)
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$lt" in cond and not value < cond["$lt"]:
                return False
        elif doc.get(key) != cond:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, keys):
        for key, direction in reversed(keys):
            self.docs.sort(key=lambda d: d[key], reverse=direction == -1)
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


class FakeInsights:
    def __init__(self):
        self.docs: list[dict] = []

    def find(self, query):
        return Cursor([d for d in self.docs if _match(d, query)])


@pytest.fixture
def insights():
    fake = FakeInsights()
    app.dependency_overrides[get_mongodb] = lambda: type("Mongo", (), {"insights": fake})()
    yield fake
    app.dependency_overrides.pop(get_mongodb, None)


async def _setup(client: AsyncClient, email: str) -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = (await client.get("/api/v1/organizations/", headers=headers)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=headers)).json()[0]
    comps = []
    for name in ("Brightdesk", "Orbit"):
        res = await client.post(
            f"/api/v1/workspaces/{ws['id']}/competitors",
            json={"name": name, "initial_urls": [{"url": f"https://{name}.example/{email}", "url_type": "pricing"}]},
            headers=headers,
        )
        comps.append(res.json())
    return {"headers": headers, "org": org, "ws": ws, "comps": comps}


def _insight(ctx: dict, comp: dict, at: datetime, url_type: str = "pricing") -> dict:
    url = comp["urls"][0]
    tenant = {
        "org_id": ctx["org"]["id"],
        "workspace_id": ctx["ws"]["id"],
        "competitor_id": comp["id"],
        "monitored_url_id": url["id"],
        "url": url["url"],
        "url_type": url_type,
        "label": None,
    }
    return {"_id": ObjectId(), **build_insight(tenant, ["Pro $39"], ["Pro $49"], at)}


T0 = datetime(2026, 11, 1, 9, 0)


@pytest.mark.asyncio
async def test_feeds_are_scoped_named_and_paginated(client: AsyncClient, insights):
    ctx = await _setup(client, "feed@example.com")
    bright, orbit = ctx["comps"]
    insights.docs += [_insight(ctx, bright, T0 + timedelta(hours=i)) for i in range(3)]
    insights.docs.append(_insight(ctx, orbit, T0 + timedelta(hours=10), url_type="blog"))
    h = ctx["headers"]

    org_feed = (await client.get(f"/api/v1/organizations/{ctx['org']['id']}/insights", headers=h)).json()
    assert [i["competitor_name"] for i in org_feed["items"]] == ["Orbit", "Brightdesk", "Brightdesk", "Brightdesk"]
    first = org_feed["items"][1]
    assert first["workspace_name"] == "General"
    assert first["added"] == ["Pro $39"] and first["removed"] == ["Pro $49"]
    assert first["headline"] == "Pricing page changed"
    assert org_feed["next_cursor"] is None

    # Cursor pages walk the feed newest first without overlap
    page1 = (await client.get(f"/api/v1/organizations/{ctx['org']['id']}/insights?limit=2", headers=h)).json()
    page2 = (
        await client.get(
            f"/api/v1/organizations/{ctx['org']['id']}/insights",
            params={"limit": 2, "cursor": page1["next_cursor"]},
            headers=h,
        )
    ).json()
    ids = [i["id"] for i in page1["items"] + page2["items"]]
    assert ids == [i["id"] for i in org_feed["items"]]
    assert page2["next_cursor"] is None

    # Scopes and filters
    comp_feed = (await client.get(f"/api/v1/competitors/{orbit['id']}/insights", headers=h)).json()
    assert [i["url_type"] for i in comp_feed["items"]] == ["blog"]
    ws_feed = (
        await client.get(f"/api/v1/workspaces/{ctx['ws']['id']}/insights", params={"url_type": "pricing"}, headers=h)
    ).json()
    assert len(ws_feed["items"]) == 3

    # Insights of a deleted competitor disappear
    await client.delete(f"/api/v1/competitors/{orbit['id']}", headers=h)
    org_feed = (await client.get(f"/api/v1/organizations/{ctx['org']['id']}/insights", headers=h)).json()
    assert {i["competitor_name"] for i in org_feed["items"]} == {"Brightdesk"}


@pytest.mark.asyncio
async def test_other_orgs_cannot_read_a_feed(client: AsyncClient, insights):
    owner = await _setup(client, "feed-owner@example.com")
    stranger = await _setup(client, "feed-stranger@example.com")
    insights.docs.append(_insight(owner, owner["comps"][0], T0))

    for path in (
        f"/api/v1/organizations/{owner['org']['id']}/insights",
        f"/api/v1/workspaces/{owner['ws']['id']}/insights",
        f"/api/v1/competitors/{owner['comps'][0]['id']}/insights",
    ):
        assert (await client.get(path, headers=stranger["headers"])).status_code == 403

    bad = await client.get(
        f"/api/v1/organizations/{owner['org']['id']}/insights", params={"cursor": "nope"}, headers=owner["headers"]
    )
    assert bad.status_code == 400


def test_headline_prompt_and_cleanup(monkeypatch):
    insight = build_insight(
        {"org_id": "o", "workspace_id": "w", "competitor_id": "c", "monitored_url_id": "u",
         "url": "https://b.example/pricing", "url_type": "pricing", "label": None},
        ["Pro — $39 per month"], ["Pro — $49 per month"], T0,
    )
    messages = headline.build_messages(insight, "Brightdesk")
    assert "Brightdesk" in messages[1]["content"]
    assert "REMOVED:\nPro — $49" in messages[1]["content"]

    class Reply:
        def __init__(self, text):
            self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]

    replies = iter(['"Brightdesk cut Pro from $49 to $39."', "   "])
    fake = type("OpenAI", (), {"chat": type("Chat", (), {"completions": type("Comp", (), {
        "create": staticmethod(lambda **kw: Reply(next(replies)))})()})()})()
    monkeypatch.setattr(headline, "get_openai", lambda: fake)

    assert headline.generate_headline(insight, "Brightdesk") == "Brightdesk cut Pro from $49 to $39"
    with pytest.raises(headline.EmptyHeadline):
        headline.generate_headline(insight, "Brightdesk")
