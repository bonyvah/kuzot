from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from app.scraping.fetcher import (
    HEADERS,
    FetchError,
    FetchResult,
    TransientFetchError,
)

NAV_TIMEOUT_MS = 30_000
SETTLE_TIMEOUT_MS = 10_000
# we only need text, so skip heavy downloads
BLOCKED_RESOURCES = {"image", "media", "font"}


def _block_heavy(route) -> None:
    if route.request.resource_type in BLOCKED_RESOURCES:
        route.abort()
    else:
        route.continue_()


def fetch_rendered(url: str) -> FetchResult:
    """Load the page in headless Chromium and return the DOM after JS ran."""
    try:
        with sync_playwright() as pw:
            # Playwright runs Chromium without its sandbox by default; the worker
            # container compensates by running as non-root (see docker-compose.yml)
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
                )
                page = context.new_page()
                page.route("**/*", _block_heavy)

                response = page.goto(
                    url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS
                )
                try:
                    page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)
                except PlaywrightTimeout:
                    pass  # busy pages never go idle; use what has rendered

                status = response.status if response else 0
                if status == 429 or status >= 500:
                    raise TransientFetchError(f"HTTP {status}")
                if status >= 400:
                    raise FetchError(f"HTTP {status}", status_code=status)

                html = page.content()
                final_url = page.url
            finally:
                browser.close()
    except PlaywrightTimeout as exc:
        raise TransientFetchError(f"Browser timeout: {exc}") from exc
    except PlaywrightError as exc:
        raise FetchError(f"Browser error: {exc}") from exc

    return FetchResult(url=final_url, status_code=status, content=html.encode("utf-8"))
