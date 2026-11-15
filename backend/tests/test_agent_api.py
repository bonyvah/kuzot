import openai
import pytest
from httpx import AsyncClient

from app.api.v1 import agent
from app.db.dependencies import get_mongodb
from app.main import app
from app.schemas.agent import AskResponse, TokenUsage


@pytest.fixture
def mongo():
    fake = object()
    app.dependency_overrides[get_mongodb] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mongodb, None)


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
    return {"headers": headers, "org_id": org_id, "ws_id": ws_id, "comp": comp.json()}


async def test_ask_answers_within_the_callers_workspace(
    client: AsyncClient, mongo, monkeypatch
):
    ctx = await _setup(client, "ask1@example.com")
    seen = {}

    async def fake_ask(question, tool_ctx):
        seen.update(question=question, ctx=tool_ctx)
        return AskResponse(
            answer="Nothing yet.",
            sources=[],
            citations_valid=True,
            tool_calls=[],
            usage=TokenUsage(),
            model="gpt-test",
        )

    monkeypatch.setattr(agent, "ask", fake_ask)
    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/ask",
        json={"question": "What changed?"},
        headers=ctx["headers"],
    )

    assert res.status_code == 200
    assert res.json()["answer"] == "Nothing yet."
    assert seen["ctx"].workspace_id == ctx["ws_id"]
    assert seen["ctx"].org_id == ctx["org_id"]
    assert seen["ctx"].competitors == {ctx["comp"]["id"]: "Acme"}
    assert seen["ctx"].monitored_url_ids == {ctx["comp"]["urls"][0]["id"]}


async def test_ask_rejects_non_members(client: AsyncClient, mongo, monkeypatch):
    owner = await _setup(client, "ask2@example.com")
    outsider = await _setup(client, "ask3@example.com")

    async def must_not_run(*_):
        raise AssertionError("agent ran for a non-member")

    monkeypatch.setattr(agent, "ask", must_not_run)
    res = await client.post(
        f"/api/v1/workspaces/{owner['ws_id']}/ask",
        json={"question": "What changed?"},
        headers=outsider["headers"],
    )
    assert res.status_code == 403


async def test_ask_maps_ai_outage_to_503(client: AsyncClient, mongo, monkeypatch):
    ctx = await _setup(client, "ask4@example.com")

    async def down(*_):
        raise openai.APIConnectionError(request=None)  # type: ignore[arg-type]

    monkeypatch.setattr(agent, "ask", down)
    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/ask",
        json={"question": "What changed?"},
        headers=ctx["headers"],
    )
    assert res.status_code == 503


async def test_ask_validates_the_question(client: AsyncClient, mongo):
    ctx = await _setup(client, "ask5@example.com")
    res = await client.post(
        f"/api/v1/workspaces/{ctx['ws_id']}/ask",
        json={"question": ""},
        headers=ctx["headers"],
    )
    assert res.status_code == 422
