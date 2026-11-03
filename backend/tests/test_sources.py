import httpx
import pytest

from app.core.config import settings
from app.models.monitored_url import URLType
from app.scraping.fetcher import FetchError, FetchResult, TransientFetchError
from app.sources import apify, telegram, web
from app.sources.base import BrowserRequired, Post, to_day
from app.sources.registry import source_for

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


def test_registry_picks_a_source_per_page_type():
    assert source_for(URLType.PRICING).name == "httpx"
    assert source_for(URLType.PRICING, use_browser=True).name == "browser"
    assert source_for(URLType.TELEGRAM).name == "telegram"
    assert source_for(URLType.TELEGRAM, use_browser=True).name == "telegram"
    assert {source_for(t).name for t in (URLType.INSTAGRAM, URLType.FACEBOOK, URLType.X)} == {
        "apify:instagram", "apify:facebook", "apify:x",
    }
    assert source_for(URLType.INSTAGRAM).respects_robots is False
    assert source_for(URLType.TELEGRAM).respects_robots is True


@pytest.mark.parametrize("value,day", [
    ("2026-11-01T08:00:00.000Z", "2026-11-01"),
    ("2026-11-02T10:30:00+06:00", "2026-11-02"),
    (1793310300, "2026-10-29"),          # Facebook: epoch seconds
    ("1793310300", "2026-10-29"),
    (1793310300000, "2026-10-29"),       # milliseconds
    ("Sat Oct 31 12:00:00 +0000 2026", "2026-10-31"),  # X
    ("yesterday", ""),
    (None, ""),
])
def test_to_day(value, day):
    assert to_day(value) == day


def test_web_source_escalates_to_the_browser(monkeypatch):
    monkeypatch.setattr(web, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=b"<html><body>Loading</body></html>"))
    with pytest.raises(BrowserRequired):
        web.HttpSource().read("https://acme.example/app")

    def forbidden(url):
        raise FetchError("HTTP 403", status_code=403)

    monkeypatch.setattr(web, "fetch_html", forbidden)
    with pytest.raises(BrowserRequired):
        web.HttpSource().read("https://acme.example/app")


def test_telegram_posts_newest_first(monkeypatch):
    monkeypatch.setattr(telegram, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=TELEGRAM))

    result = telegram.TelegramSource().read("https://t.me/s/acme_news")

    assert result.via == "telegram"
    assert result.paragraphs == [
        "2026-11-02 · New: Pro plan now $39 per month · https://t.me/acme_news/43",
        "2026-10-01 · Old post: summer sale · https://t.me/acme_news/41",
    ]
    assert result.text == "\n".join(result.paragraphs)


def test_telegram_without_posts_says_why(monkeypatch):
    monkeypatch.setattr(telegram, "fetch_html", lambda url: FetchResult(url=url, status_code=200, content=b"<html></html>"))
    with pytest.raises(FetchError, match="public Telegram channel"):
        telegram.TelegramSource().read("https://t.me/s/private")


def test_apify_sources_need_a_token(monkeypatch):
    monkeypatch.setattr(settings, "APIFY_TOKEN", None)
    with pytest.raises(apify.ProviderMissing, match="APIFY_TOKEN"):
        apify.InstagramSource().read("https://instagram.com/acme")


# what each actor actually returned in a live run (trimmed)
ITEMS = {
    apify.InstagramSource: ({"caption": "Spring drop", "timestamp": "2026-11-01T08:00:00.000Z", "url": "https://instagram.com/p/1"},
                            "2026-11-01 · Spring drop · https://instagram.com/p/1"),
    apify.FacebookSource: ({"text": "Welcome, Vietnam", "time": 1793310300, "url": "https://facebook.com/NASA/posts/1"},
                           "2026-10-29 · Welcome, Vietnam · https://facebook.com/NASA/posts/1"),
    apify.XSource: ({"fullText": "Happy Halloween!", "createdAt": "Sat Oct 31 12:00:00 +0000 2026", "url": "https://x.com/NASA/status/1"},
                    "2026-10-31 · Happy Halloween! · https://x.com/NASA/status/1"),
}


@pytest.mark.parametrize("source_cls", list(ITEMS))
def test_apify_items_become_posts(monkeypatch, source_cls):
    item, line = ITEMS[source_cls]
    monkeypatch.setattr(settings, "APIFY_TOKEN", "test-token")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"])
        return httpx.Response(200, json=[item, {"error": "not_found"}, {}], request=httpx.Request("POST", url))

    monkeypatch.setattr(apify.httpx, "post", fake_post)
    source = source_cls()
    result = source.read("https://example.com/acme")

    assert seen["url"].endswith(f"/acts/{source.actor()}/run-sync-get-dataset-items")
    assert seen["auth"] == "Bearer test-token"
    assert result.paragraphs == [line]
    assert result.via == source.name


@pytest.mark.parametrize("status,error", [(429, TransientFetchError), (502, TransientFetchError), (401, FetchError)])
def test_apify_errors(monkeypatch, status, error):
    monkeypatch.setattr(settings, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(apify.httpx, "post", lambda url, **kw: httpx.Response(status, request=httpx.Request("POST", url)))
    with pytest.raises(error):
        apify.XSource().read("https://x.com/acme")


def test_post_line_skips_missing_parts():
    assert Post(day="", text="  hello\n world ", link="").line() == "hello world"
