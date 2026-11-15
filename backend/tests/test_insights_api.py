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
            if "$nin" in cond and value in cond["$nin"]:
                return False
            if "$ne" in cond and value == cond["$ne"]:
                return False
            if "$lt" in cond and not value < cond["$lt"]:
                return False
            if "$gt" in cond and not value > cond["$gt"]:
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


class FakeCollection:
    """The bits of a Motor collection the insight endpoints use."""

    def __init__(self):
        self.docs: list[dict] = []

    def find(self, query, projection=None):
        return Cursor([d for d in self.docs if _match(d, query)])

    async def find_one(self, query):
        return next((d for d in self.docs if _match(d, query)), None)

    async def update_one(self, query, update, upsert=False):
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self.docs.append(doc)
            doc.update(update.get("$setOnInsert", {}))
        doc.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            doc.pop(key, None)
        for key, value in update.get("$min", {}).items():
            if doc.get(key) is None or value < doc[key]:
                doc[key] = value

    async def bulk_write(self, ops, ordered=True):
        for op in ops:
            await self.update_one(op._filter, op._doc, upsert=op._upsert)

    def aggregate(self, pipeline):
        match, group = pipeline[0]["$match"], pipeline[1]["$group"]
        fields = {name: ref.lstrip("$") for name, ref in group["_id"].items()}
        counts: dict[tuple, int] = {}
        for d in self.docs:
            if _match(d, match):
                key = tuple(d[f] for f in fields.values())
                counts[key] = counts.get(key, 0) + 1
        return Cursor([{"_id": dict(zip(fields, key)), "n": n} for key, n in counts.items()])


class FakeMongo:
    def __init__(self):
        self.insights = FakeCollection()
        self.insight_states = FakeCollection()
        self.insight_cursors = FakeCollection()


@pytest.fixture
def mongo():
    fake = FakeMongo()
    app.dependency_overrides[get_mongodb] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mongodb, None)


@pytest.fixture
def insights(mongo):
    return mongo.insights


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
    assert first["diff"] == [[{"op": "removed", "text": "Pro $49"}, {"op": "added", "text": "Pro $39"}]]
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
    content = headline.build_messages(insight, "Brightdesk")[1].get("content")
    assert isinstance(content, str)
    assert "Brightdesk" in content
    assert "- Pro — $49 per month\n+ Pro — $39 per month" in content

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


async def _start_unread(client: AsyncClient, mongo: FakeMongo, ctx: dict, since: datetime) -> None:
    """Pretend the user last read everything at `since`."""
    me = (await client.get("/api/v1/auth/me", headers=ctx["headers"])).json()
    mongo.insight_cursors.docs.append({"user_id": me["id"], "org_id": ctx["org"]["id"], "seen_until": since})


@pytest.mark.asyncio
async def test_read_state_tabs_and_counts(client: AsyncClient, mongo):
    ctx = await _setup(client, "reads@example.com")
    bright, orbit = ctx["comps"]
    org, h = ctx["org"]["id"], ctx["headers"]
    docs = [_insight(ctx, bright, T0 + timedelta(hours=i)) for i in range(3)]
    docs.append(_insight(ctx, orbit, T0 + timedelta(hours=10)))
    mongo.insights.docs += docs
    await _start_unread(client, mongo, ctx, T0 - timedelta(hours=1))
    ids = [str(d["_id"]) for d in docs]

    async def feed(state: str) -> list[dict]:
        return (await client.get(f"/api/v1/organizations/{org}/insights", params={"state": state}, headers=h)).json()["items"]

    async def counts() -> dict:
        return (await client.get(f"/api/v1/organizations/{org}/insights/counts", headers=h)).json()

    async def act(action: str, *which: str) -> list[dict]:
        res = await client.post("/api/v1/insights/states", json={"ids": list(which), "action": action}, headers=h)
        assert res.status_code == 200, res.text
        return res.json()

    assert await counts() == {
        "total": 4,
        "workspaces": {ctx["ws"]["id"]: 4},
        "competitors": {bright["id"]: 3, orbit["id"]: 1},
    }
    unread = await feed("unread")
    assert len(unread) == 4 and not any(i["state"]["seen"] for i in unread)

    # Seen and opened leave the unread tab
    assert (await act("seen", ids[2]))[0]["state"] == {"seen": True, "opened": False, "saved": False, "dismissed": False}
    assert (await act("open", ids[1]))[0]["state"]["opened"] is True
    assert [i["id"] for i in await feed("unread")] == [ids[3], ids[0]]
    assert (await counts())["competitors"] == {bright["id"]: 1, orbit["id"]: 1}

    # Saved tab
    await act("save", ids[0])
    saved = await feed("saved")
    assert [i["id"] for i in saved] == [ids[0]] and saved[0]["state"]["saved"]

    # Dismissed: gone from all and unread, read, and no longer saved; restore brings it back read
    await act("save", ids[3])
    await act("dismiss", ids[3])
    assert ids[3] not in [i["id"] for i in await feed("all")]
    assert ids[3] not in [i["id"] for i in await feed("saved")]
    assert orbit["id"] not in (await counts())["competitors"]
    await act("restore", ids[3])
    back = next(i for i in await feed("all") if i["id"] == ids[3])
    assert back["state"] == {"seen": True, "opened": False, "saved": False, "dismissed": False}

    # Mark one competitor read
    res = await client.post(f"/api/v1/organizations/{org}/insights/read", json={"competitor_id": bright["id"]}, headers=h)
    assert res.json() == {"total": 0, "workspaces": {}, "competitors": {}}
    assert await feed("unread") == []

    # Mark the whole organization read
    mongo.insights.docs.append(_insight(ctx, orbit, T0 + timedelta(hours=20)))
    assert (await counts())["total"] == 1
    res = await client.post(f"/api/v1/organizations/{org}/insights/read", json={}, headers=h)
    assert res.json()["total"] == 0
    assert all(i["state"]["seen"] for i in await feed("all"))

    # Workspace and competitor feeds take the same tabs
    ws_unread = await client.get(f"/api/v1/workspaces/{ctx['ws']['id']}/insights", params={"state": "unread"}, headers=h)
    assert ws_unread.json()["items"] == []
    comp_saved = await client.get(f"/api/v1/competitors/{bright['id']}/insights", params={"state": "saved"}, headers=h)
    assert [i["id"] for i in comp_saved.json()["items"]] == [ids[0]]


@pytest.mark.asyncio
async def test_insights_before_joining_count_as_read(client: AsyncClient, mongo):
    ctx = await _setup(client, "reads-join@example.com")
    mongo.insights.docs.append(_insight(ctx, ctx["comps"][0], T0))
    org, h = ctx["org"]["id"], ctx["headers"]
    assert (await client.get(f"/api/v1/organizations/{org}/insights/counts", headers=h)).json()["total"] == 0
    item = (await client.get(f"/api/v1/organizations/{org}/insights", headers=h)).json()["items"][0]
    assert item["state"]["seen"] is True


@pytest.mark.asyncio
async def test_states_are_checked(client: AsyncClient, mongo):
    owner = await _setup(client, "reads-owner@example.com")
    stranger = await _setup(client, "reads-stranger@example.com")
    doc = _insight(owner, owner["comps"][0], T0)
    mongo.insights.docs.append(doc)

    def post(body, headers):
        return client.post("/api/v1/insights/states", json=body, headers=headers)

    assert (await post({"ids": [str(doc["_id"])], "action": "seen"}, stranger["headers"])).status_code == 403
    assert (await post({"ids": ["nope"], "action": "seen"}, owner["headers"])).status_code == 400
    assert (await post({"ids": [str(ObjectId())], "action": "seen"}, owner["headers"])).status_code == 404
    assert (await post({"ids": [str(doc["_id"])], "action": "explode"}, owner["headers"])).status_code == 422
    assert mongo.insight_states.docs == []
    org = owner["org"]["id"]
    assert (await client.get(f"/api/v1/organizations/{org}/insights/counts", headers=stranger["headers"])).status_code == 403
    assert (await client.post(f"/api/v1/organizations/{org}/insights/read", json={}, headers=stranger["headers"])).status_code == 403
