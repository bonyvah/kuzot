"""Posts from social channels, as text the change detector can diff.

Telegram public channels are read from their web view (t.me/s/<name>).
Instagram, Facebook and X block anonymous scrapers, so they go through a
social data provider; the first adapter is Apify. Each post becomes one
line ("date · text · link"), so a new post shows up as an added line.
"""

from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.monitored_url import URLType
from app.scraping.extractor import normalize_text
from app.scraping.fetcher import FetchError, TransientFetchError, fetch_html

SOCIAL_TYPES = {URLType.TELEGRAM, URLType.INSTAGRAM, URLType.FACEBOOK, URLType.X}
PROVIDER_TYPES = {URLType.INSTAGRAM, URLType.FACEBOOK, URLType.X}

MAX_POSTS = 20  # recent posts per run: enough to catch new ones, cheap per request
APIFY_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
APIFY_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)

NAMES = {URLType.INSTAGRAM: "Instagram", URLType.FACEBOOK: "Facebook", URLType.X: "X"}


class ProviderMissing(FetchError):
    """The social data provider isn't configured, so the page can't be read."""


@dataclass
class Post:
    date: str
    text: str
    link: str

    def line(self) -> str:
        return " · ".join(part for part in (self.date, normalize_text(self.text), self.link) if part)


def read_posts(url_type: URLType, url: str) -> list[Post]:
    if url_type == URLType.TELEGRAM:
        return telegram_posts(url)
    return provider_posts(url_type, url)


# ── Telegram ─────────────────────────────────────────────────────────────────

def telegram_posts(url: str) -> list[Post]:
    page = fetch_html(url)
    soup = BeautifulSoup(page.content, "lxml")
    posts = []
    for message in soup.select(".tgme_widget_message[data-post]"):
        body = message.select_one(".tgme_widget_message_text")
        stamp = message.select_one("time[datetime]")
        text = body.get_text("\n") if body else ""
        if not text.strip():
            continue  # photos or stickers without a caption
        posts.append(
            Post(
                date=(stamp["datetime"][:10] if stamp else ""),
                text=text,
                link=f"https://t.me/{message['data-post']}",
            )
        )
    if not posts:
        raise FetchError("No public posts found: is this a public Telegram channel?")
    return posts[-MAX_POSTS:][::-1]  # the web view lists oldest first


# ── Instagram, Facebook, X via Apify ─────────────────────────────────────────

def _actor_input(url_type: URLType, url: str) -> tuple[str, dict]:
    if url_type == URLType.INSTAGRAM:
        return settings.APIFY_INSTAGRAM_ACTOR, {
            "directUrls": [url], "resultsType": "posts", "resultsLimit": MAX_POSTS,
        }
    if url_type == URLType.FACEBOOK:
        return settings.APIFY_FACEBOOK_ACTOR, {"startUrls": [{"url": url}], "resultsLimit": MAX_POSTS}
    return settings.APIFY_X_ACTOR, {"startUrls": [url], "maxItems": MAX_POSTS, "sort": "Latest"}


def _first(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def provider_posts(url_type: URLType, url: str) -> list[Post]:
    name = NAMES[url_type]
    if not settings.APIFY_TOKEN:
        raise ProviderMissing(f"{name} pages need the Apify integration: add APIFY_TOKEN to backend/.env")
    actor, actor_input = _actor_input(url_type, url)
    try:
        response = httpx.post(
            APIFY_URL.format(actor=actor),
            headers={"Authorization": f"Bearer {settings.APIFY_TOKEN}"},
            json=actor_input,
            timeout=APIFY_TIMEOUT,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise TransientFetchError(f"Apify: {type(exc).__name__}") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise TransientFetchError(f"Apify: HTTP {response.status_code}")
    if response.status_code >= 400:
        raise FetchError(f"Apify refused the request (HTTP {response.status_code})", status_code=response.status_code)

    posts = []
    for item in response.json()[:MAX_POSTS]:
        if not isinstance(item, dict) or item.get("error"):
            continue
        text = _first(item, "caption", "text", "fullText", "message", "postText")
        if not text.strip():
            continue
        posts.append(
            Post(
                date=_first(item, "timestamp", "time", "createdAt", "date")[:10],
                text=text,
                link=_first(item, "url", "postUrl", "twitterUrl", "link"),
            )
        )
    if not posts:
        raise FetchError(f"No public {name} posts were returned for this page")
    return posts
