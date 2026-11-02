import json

import httpx
import pytest
from httpx import AsyncClient

from app.api.v1 import discovery as discovery_api
from app.discovery import search, select, service
from app.discovery.links import Candidate, classify, from_hint, normalize
from app.discovery.service import Discovery, Found, Hint, discover
from app.models.monitored_url import URLType
from app.scraping.fetcher import FetchResult

HOME = b"""<html><body>
<a href="/">Home</a><a href="/pricing">Pricing</a><a href="/blog/">Blog</a>
<a href="/legal/terms">Terms</a><a href="https://docs.acme.io/start">Docs</a>
<a href="https://t.me/acme_news">Telegram</a><a href="https://www.instagram.com/acme/?utm_source=site">IG</a>
<a href="https://twitter.com/intent/tweet?text=hi">Share</a><a href="https://other.com/x">Partner</a>
<a href="mailto:hi@acme.io">Mail</a>
</body></html>"""
SITEMAP = "<urlset><url><loc>https://acme.io/changelog</loc></url><url><loc>https://acme.io/careers</loc></url></urlset>"


def test_classify_and_normalize():
    host = "acme.io"
    assert classify("https://acme.io/", host) == (URLType.HOMEPAGE, None)
    assert classify("https://acme.io/en/pricing", host) == (URLType.PRICING, None)
    assert classify("https://docs.acme.io/x", host) == (URLType.DOCS, None)
    assert classify("https://www.linkedin.com/company/acme", host) == (URLType.OTHER, "LinkedIn")
    assert classify("https://x.com/intent/tweet", host) is None
    assert classify("https://other.com/pricing", host) is None
    assert normalize("https://Acme.io/a?utm_source=x&id=2#top") == "https://acme.io/a?id=2"
    assert normalize("javascript:void(0)") is None
    assert from_hint(URLType.TELEGRAM, "@acme") == "https://t.me/s/acme"
    assert from_hint(URLType.INSTAGRAM, "instagram.com/acme") == "https://instagram.com/acme"


@pytest.fixture
def site(monkeypatch):
    monkeypatch.setattr(service, "robots_allows", lambda url: True)
    monkeypatch.setattr(service, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=HOME))

    def fake_get(url, **kw):
        return httpx.Response(200, text=SITEMAP, request=httpx.Request("GET", url))

    monkeypatch.setattr(service.httpx, "get", fake_get)


def test_without_model_keeps_pages_matched_by_address(site, monkeypatch):
    monkeypatch.setattr(service, "pick", lambda *a, **k: None)
    monkeypatch.setattr(search, "enabled", lambda: False)

    result = discover(
        name="Acme",
        website="https://acme.io",
        hints=[Hint(URLType.X, "@acme_x"), Hint(URLType.FACEBOOK)],
    )

    by_url = {p.url: p for p in result.pages}
    assert result.pages[0].url == "https://acme.io/" and result.pages[0].url_type == URLType.HOMEPAGE
    assert by_url["https://acme.io/pricing"].url_type == URLType.PRICING
    assert by_url["https://acme.io/changelog"].url_type == URLType.CHANGELOG  # from the sitemap
    assert by_url["https://t.me/s/acme_news"].url_type == URLType.TELEGRAM
    assert by_url["https://x.com/acme_x"].source == "hint"
    assert "https://acme.io/legal/terms" not in by_url and "https://other.com/x" not in by_url
    assert any("Web search is off" in n for n in result.notes)
    assert any("AI selection is unavailable" in n for n in result.notes)


def test_search_and_exclusions(site, monkeypatch):
    queries = []
    monkeypatch.setattr(search, "enabled", lambda: True)
    monkeypatch.setattr(search, "search", lambda q: queries.append(q) or [{"url": "https://facebook.com/acmeio", "title": "Acme", "content": ""}])
    monkeypatch.setattr(service, "pick", lambda cands, **k: [(c, "useful") for c in cands])

    result = discover(name="Acme", website="https://acme.io", hints=[Hint(URLType.FACEBOOK)], exclude={"https://acme.io/pricing"})

    urls = {p.url for p in result.pages}
    assert queries == ["Acme Facebook page"]
    assert "https://facebook.com/acmeio" in urls
    assert "https://acme.io/pricing" not in urls


def test_model_can_only_pick_listed_candidates(monkeypatch):
    cands = [Candidate("https://acme.io/", URLType.HOMEPAGE), Candidate("https://acme.io/plans", URLType.OTHER)]
    answer = {"pages": [
        {"index": 1, "url_type": "pricing", "label": "ignored", "reason": "plans page"},
        {"index": 7, "url_type": "blog", "label": None, "reason": "made up"},
        {"index": 1, "url_type": "blog", "label": None, "reason": "duplicate"},
    ]}

    class Completions:
        @staticmethod
        def create(**kw):
            msg = type("M", (), {"content": json.dumps(answer)})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()

    monkeypatch.setattr(select, "get_openai", lambda: type("O", (), {"chat": type("Ch", (), {"completions": Completions})()})())
    picked = select.pick(cands, name="Acme", website=None, description=None, notes=None, looking_for=None)

    assert [(c.url, c.url_type, c.label, r) for c, r in picked] == [("https://acme.io/plans", URLType.PRICING, None, "plans page")]


@pytest.mark.asyncio
async def test_discover_endpoints(client: AsyncClient, monkeypatch):
    calls = []

    def fake_discover(**kw):
        calls.append(kw)
        return Discovery(pages=[Found("https://acme.io/pricing", URLType.PRICING, None, "Pricing page", "site")], notes=[])

    monkeypatch.setattr(discovery_api, "discover", fake_discover)
    await client.post("/api/v1/auth/register", json={"email": "disc@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "disc@example.com", "password": "Password123!"})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = (await client.get("/api/v1/organizations/", headers=h)).json()[0]
    ws = (await client.get(f"/api/v1/organizations/{org['id']}/workspaces", headers=h)).json()[0]

    res = await client.post(
        f"/api/v1/workspaces/{ws['id']}/discover",
        json={"name": "Acme", "website": "https://acme.io", "hints": [{"url_type": "telegram", "value": "@acme"}]},
        headers=h,
    )
    assert res.status_code == 200, res.text
    assert res.json()["pages"][0]["url_type"] == "pricing"
    assert calls[0]["hints"][0].url_type == URLType.TELEGRAM

    comp = (await client.post(
        f"/api/v1/workspaces/{ws['id']}/competitors",
        json={"name": "Acme", "website_url": "https://acme.io", "initial_urls": [{"url": "https://acme.io/disc-home"}]},
        headers=h,
    )).json()
    res = await client.post(f"/api/v1/competitors/{comp['id']}/discover", json={"looking_for": "pricing page"}, headers=h)
    assert res.status_code == 200
    assert calls[1]["looking_for"] == "pricing page" and calls[1]["exclude"] == {"https://acme.io/disc-home"}

    other = await client.post("/api/v1/auth/register", json={"email": "disc-x@example.com", "password": "Password123!"})
    login = await client.post("/api/v1/auth/login", json={"email": "disc-x@example.com", "password": "Password123!"})
    denied = await client.post(
        f"/api/v1/workspaces/{ws['id']}/discover", json={"name": "Acme"},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert other.status_code == 201 and denied.status_code == 403
