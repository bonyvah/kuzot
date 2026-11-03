"""Instagram, Facebook and X through Apify actors.

These platforms block anonymous scrapers, so a social data provider reads
them for us. Each platform is a small subclass: which actor to run, what
input it takes, and how to read a post out of its results.
"""

import httpx

from app.core.config import settings
from app.scraping.fetcher import FetchError, TransientFetchError
from app.sources.base import Post, Source, SourceResult, posts_result, to_day

MAX_POSTS = 20  # recent posts per run: enough to catch new ones, cheap per request
RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)


class ProviderMissing(FetchError):
    """The provider isn't configured, so the page can't be read."""


def _first(item: dict, *keys: str):
    for key in keys:
        if item.get(key):
            return item[key]
    return None


class ApifySource(Source):
    respects_robots = False  # Apify fetches, not us
    platform: str  # shown to people, e.g. "Instagram"

    @property
    def name(self) -> str:
        return f"apify:{self.platform.lower()}"

    def actor(self) -> str:
        raise NotImplementedError

    def actor_input(self, url: str) -> dict:
        raise NotImplementedError

    def post(self, item: dict) -> Post | None:
        raise NotImplementedError

    def read(self, url: str) -> SourceResult:
        if not settings.APIFY_TOKEN:
            raise ProviderMissing(
                f"{self.platform} pages need the Apify integration: add APIFY_TOKEN to backend/.env"
            )
        try:
            response = httpx.post(
                RUN_URL.format(actor=self.actor()),
                headers={"Authorization": f"Bearer {settings.APIFY_TOKEN}"},
                json=self.actor_input(url),
                timeout=TIMEOUT,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TransientFetchError(f"Apify: {type(exc).__name__}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise TransientFetchError(f"Apify: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise FetchError(f"Apify refused the request (HTTP {response.status_code})", status_code=response.status_code)

        items = response.json()
        posts = [
            p for item in (items if isinstance(items, list) else [])[:MAX_POSTS]
            if isinstance(item, dict) and not item.get("error") and (p := self.post(item)) and p.text.strip()
        ]
        if not posts:
            raise FetchError(f"No public {self.platform} posts were returned for this page")
        return posts_result(url, posts, self.name)


class InstagramSource(ApifySource):
    platform = "Instagram"

    def actor(self) -> str:
        return settings.APIFY_INSTAGRAM_ACTOR

    def actor_input(self, url: str) -> dict:
        return {"directUrls": [url], "resultsType": "posts", "resultsLimit": MAX_POSTS}

    def post(self, item: dict) -> Post:
        return Post(day=to_day(item.get("timestamp")), text=item.get("caption") or "", link=item.get("url") or "")


class FacebookSource(ApifySource):
    platform = "Facebook"

    def actor(self) -> str:
        return settings.APIFY_FACEBOOK_ACTOR

    def actor_input(self, url: str) -> dict:
        return {"startUrls": [{"url": url}], "resultsLimit": MAX_POSTS}

    def post(self, item: dict) -> Post:
        return Post(
            day=to_day(_first(item, "timestamp", "time")),  # epoch seconds, or ISO
            text=_first(item, "text", "message") or "",
            link=_first(item, "url", "topLevelUrl", "facebookUrl") or "",
        )


class XSource(ApifySource):
    platform = "X"

    def actor(self) -> str:
        return settings.APIFY_X_ACTOR

    def actor_input(self, url: str) -> dict:
        return {"startUrls": [url], "maxItems": MAX_POSTS, "sort": "Latest"}

    def post(self, item: dict) -> Post:
        return Post(
            day=to_day(item.get("createdAt")),  # "Sat Oct 31 12:00:00 +0000 2026"
            text=_first(item, "fullText", "text") or "",
            link=_first(item, "url", "twitterUrl") or "",
        )
