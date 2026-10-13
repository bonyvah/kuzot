from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,ky;q=0.7",
}

TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
MAX_BYTES = 5 * 1024 * 1024  # refuse pages over 5MB


class FetchError(Exception):
    """Permanent failure: retrying won't help (404, 403, wrong content type)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TransientFetchError(Exception):
    """Temporary failure: worth retrying (timeout, 5xx, 429, network)."""


@dataclass
class FetchResult:
    url: str          # final URL after redirects
    status_code: int
    content: bytes


@retry(
    retry=retry_if_exception_type(TransientFetchError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def fetch_html(url: str) -> FetchResult:
    try:
        with httpx.Client(
            headers=HEADERS, timeout=TIMEOUT, follow_redirects=True
        ) as client:
            response = client.get(url)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise TransientFetchError(f"{type(exc).__name__}: {exc}") from exc

    status = response.status_code
    if status == 429 or status >= 500:
        raise TransientFetchError(f"HTTP {status}")
    if status >= 400:
        raise FetchError(f"HTTP {status}", status_code=status)

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        raise FetchError(f"Not HTML: {content_type}")

    if len(response.content) > MAX_BYTES:
        raise FetchError("Page too large")

    return FetchResult(
        url=str(response.url), status_code=status, content=response.content
    )