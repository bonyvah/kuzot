"""robots.txt per RFC 9309: may KuzotBot fetch this URL?"""

from urllib.parse import urlsplit

import httpx
from protego import Protego

from app.scraping.fetcher import BOT_NAME, HEADERS, TIMEOUT

MAX_ROBOTS_BYTES = 500 * 1024  # RFC 9309: parsers must handle at least 500 KiB


class RobotsUnreachable(Exception):
    """robots.txt couldn't be read (5xx, 429, network). RFC 9309: assume disallow."""


def robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def fetch_robots_txt(url: str) -> str:
    """The robots.txt governing url; "" when the site has none."""
    try:
        with httpx.Client(
            headers=HEADERS, timeout=TIMEOUT, follow_redirects=True
        ) as client:
            response = client.get(robots_url(url))
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise RobotsUnreachable(f"{type(exc).__name__}: {exc}") from exc

    status = response.status_code
    if status == 429 or status >= 500:
        raise RobotsUnreachable(f"HTTP {status}")
    if status >= 400:
        return ""  # RFC 9309: 4xx means no rules, crawling is allowed
    return response.content[:MAX_ROBOTS_BYTES].decode("utf-8", errors="replace")


def is_allowed(robots_txt: str, url: str) -> bool:
    return Protego.parse(robots_txt).can_fetch(url, BOT_NAME)
