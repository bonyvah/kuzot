import httpx
import pytest

from app.core.config import settings
from app.models.monitored_url import URLType
from app.scraping import social
from app.scraping.fetcher import FetchError, FetchResult, TransientFetchError

TELEGRAM = b"""<html><body>
<div class="tgme_widget_message" data-post="acme_news/41">
  <div class="tgme_widget_message_text">Old post: summer sale</div>
  <time datetime="2026-10-01T09:00:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="acme_news/42"><time datetime="2026-10-02T09:00:00+00:00"></time></div>
<div class="tgme_widget_message" data-post="acme_news/43">
  <div class="tgme_widget_message_text">New: Pro plan now <b>$39</b><br>per month</div>
  <time datetime="2026-11-02T10:30:00+00:00"></time>
</div>
</body></html>"""


def test_telegram_posts_newest_first(monkeypatch):
    monkeypatch.setattr(social, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=TELEGRAM))

    posts = social.telegram_posts("https://t.me/s/acme_news")

    assert [p.line() for p in posts] == [
        "2026-11-02 · New: Pro plan now $39 per month · https://t.me/acme_news/43",
        "2026-10-01 · Old post: summer sale · https://t.me/acme_news/41",
    ]


def test_telegram_without_posts_says_why(monkeypatch):
    monkeypatch.setattr(social, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=b"<html></html>"))
    with pytest.raises(FetchError, match="public Telegram channel"):
        social.telegram_posts("https://t.me/s/private")


def test_providers_need_a_token(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_TOKEN", None)
    with pytest.raises(social.ProviderMissing, match="APIFY_TOKEN"):
        social.read_posts(URLType.INSTAGRAM, "https://instagram.com/acme")


def test_apify_items_become_posts(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_TOKEN", "test-token")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return httpx.Response(200, json=[
            {"caption": "Spring drop is here", "timestamp": "2026-11-01T08:00:00.000Z", "url": "https://instagram.com/p/1"},
            {"error": "not_found"},
            {"caption": ""},
        ], request=httpx.Request("POST", url))

    monkeypatch.setattr(social.httpx, "post", fake_post)
    posts = social.read_posts(URLType.INSTAGRAM, "https://instagram.com/acme")

    assert seen["url"].endswith("/acts/apify~instagram-scraper/run-sync-get-dataset-items")
    assert seen["auth"] == "Bearer test-token"
    assert seen["body"]["directUrls"] == ["https://instagram.com/acme"]
    assert [p.line() for p in posts] == ["2026-11-01 · Spring drop is here · https://instagram.com/p/1"]


@pytest.mark.parametrize("status,error", [(429, TransientFetchError), (502, TransientFetchError), (401, FetchError)])
def test_apify_errors(monkeypatch, status, error):
    monkeypatch.setattr(settings, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(social.httpx, "post", lambda url, **kw: httpx.Response(status, request=httpx.Request("POST", url)))
    with pytest.raises(error):
        social.read_posts(URLType.X, "https://x.com/acme")
