"""Web pages: a plain HTTP fetch, or a headless browser for pages that need JS."""

from app.scraping.browser import fetch_rendered
from app.scraping.extractor import extract_text, is_thin, normalize_text, split_paragraphs
from app.scraping.fetcher import FetchError, fetch_html
from app.sources.base import BrowserRequired, Source, SourceResult


def _page_result(content: bytes, url: str, via: str) -> SourceResult | None:
    """Main text of a page; None when there's too little to be the real page."""
    raw = extract_text(content)
    if raw is None or is_thin(raw):
        return None
    return SourceResult(url=url, text=normalize_text(raw), paragraphs=split_paragraphs(raw), via=via)


class HttpSource(Source):
    name = "httpx"

    def read(self, url: str) -> SourceResult:
        try:
            page = fetch_html(url)
        except FetchError as exc:
            # 403 is often an anti-bot block that a real browser gets past
            if exc.status_code == 403:
                raise BrowserRequired() from exc
            raise
        result = _page_result(page.content, page.url, self.name)
        if result is None:
            raise BrowserRequired()  # probably a JavaScript shell
        return result


class BrowserSource(Source):
    name = "browser"

    def read(self, url: str) -> SourceResult:
        page = fetch_rendered(url)
        result = _page_result(page.content, page.url, self.name)
        if result is None:
            raise FetchError("Too little text extracted even after browser rendering")
        return result

