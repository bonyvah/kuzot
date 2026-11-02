import httpx
import pytest

from app.scraping import robots
from app.scraping.fetcher import HEADERS
from app.scraping.robots import (
    RobotsUnreachable,
    fetch_robots_txt,
    is_allowed,
    robots_url,
)


def use_handler(monkeypatch, handler):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(robots.httpx, "Client", factory)


def test_user_agent_is_honest():
    ua = HEADERS["User-Agent"]
    assert ua.startswith("KuzotBot/1.0 (+")
    assert "Mozilla" not in ua and "Chrome" not in ua


def test_robots_url_is_site_root():
    assert robots_url("https://acme.com:8443/a/b?x=1") == (
        "https://acme.com:8443/robots.txt"
    )


def test_fetch_returns_body_and_sends_our_user_agent(monkeypatch):
    seen = {}

    def handler(req):
        seen["path"] = req.url.path
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200, text="User-agent: *\nDisallow: /x\n")

    use_handler(monkeypatch, handler)

    assert "Disallow: /x" in fetch_robots_txt("https://acme.com/pricing")
    assert seen["path"] == "/robots.txt"
    assert seen["ua"].startswith("KuzotBot/")


@pytest.mark.parametrize("status", [401, 403, 404, 410])
def test_4xx_means_no_rules(monkeypatch, status):
    use_handler(monkeypatch, lambda req: httpx.Response(status))
    body = fetch_robots_txt("https://acme.com/")
    assert body == ""
    assert is_allowed(body, "https://acme.com/anything")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_server_errors_are_unreachable(monkeypatch, status):
    use_handler(monkeypatch, lambda req: httpx.Response(status))
    with pytest.raises(RobotsUnreachable, match=f"HTTP {status}"):
        fetch_robots_txt("https://acme.com/")


def test_network_error_is_unreachable(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("refused")

    use_handler(monkeypatch, handler)
    with pytest.raises(RobotsUnreachable, match="ConnectError"):
        fetch_robots_txt("https://acme.com/")


RULES = """
User-agent: *
Disallow: /
Allow: /pricing
Disallow: /*?session=

User-agent: KuzotBot
Disallow: /internal
"""


def test_our_group_overrides_the_wildcard_group():
    # KuzotBot has its own group, so only /internal is off limits for us
    assert is_allowed(RULES, "https://acme.com/blog")
    assert not is_allowed(RULES, "https://acme.com/internal/x")


def test_wildcard_group_uses_longest_match_and_patterns():
    rules = RULES.split("User-agent: KuzotBot")[0]  # only the * group
    assert is_allowed(rules, "https://acme.com/pricing")
    assert not is_allowed(rules, "https://acme.com/blog")
    assert not is_allowed(rules, "https://acme.com/pricing?session=1")


def test_disallow_all_blocks_us():
    assert not is_allowed("User-agent: *\nDisallow: /\n", "https://acme.com/")
