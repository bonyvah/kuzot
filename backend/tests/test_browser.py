from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from app.scraping import browser
from app.scraping.fetcher import FetchError, TransientFetchError


class FakePage:
    def __init__(self, status=200, html="<html>rendered</html>", idle_timeout=False,
                 goto_error=None):
        self.status = status
        self.html = html
        self.idle_timeout = idle_timeout
        self.goto_error = goto_error
        self.url = "https://example.com/final"
        self.route_pattern = None
        self.route_handler = None

    def route(self, pattern, handler):
        self.route_pattern, self.route_handler = pattern, handler

    def goto(self, url, wait_until, timeout):
        if self.goto_error:
            raise self.goto_error
        return SimpleNamespace(status=self.status)

    def wait_for_load_state(self, state, timeout):
        if self.idle_timeout:
            raise PlaywrightTimeout("never idle")

    def content(self):
        return self.html


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.closed = False
        self.context_kwargs = None

    def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        return SimpleNamespace(new_page=lambda: self.page)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_playwright(monkeypatch):
    state = {}

    def install(page, launch_error=None):
        fake_browser = FakeBrowser(page)
        state["browser"] = fake_browser

        def launch(**kwargs):
            if launch_error:
                raise launch_error
            return fake_browser

        @contextmanager
        def fake_sync_playwright():
            yield SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        monkeypatch.setattr(browser, "sync_playwright", fake_sync_playwright)
        return state

    return install


def test_returns_rendered_dom_as_utf8_bytes(fake_playwright):
    state = fake_playwright(FakePage(html="<html>Привет</html>"))

    result = browser.fetch_rendered("https://example.com/")

    assert result.content == "<html>Привет</html>".encode()
    assert result.url == "https://example.com/final"
    assert result.status_code == 200
    assert state["browser"].closed is True
    assert "ru" in state["browser"].context_kwargs["extra_http_headers"][
        "Accept-Language"
    ]


def test_page_that_never_goes_idle_is_still_used(fake_playwright):
    fake_playwright(FakePage(idle_timeout=True))
    assert browser.fetch_rendered("https://example.com/").content


def test_heavy_resources_are_blocked(fake_playwright):
    page = FakePage()
    fake_playwright(page)
    browser.fetch_rendered("https://example.com/")

    actions = []

    def route_for(kind) -> SimpleNamespace:
        return SimpleNamespace(
            request=SimpleNamespace(resource_type=kind),
            abort=lambda: actions.append(("abort", kind)),
            continue_=lambda: actions.append(("continue", kind)),
        )

    for kind in ["image", "font", "media", "document", "script"]:
        assert page.route_handler is not None
        page.route_handler(route_for(kind))

    assert page.route_pattern == "**/*"
    assert actions == [
        ("abort", "image"),
        ("abort", "font"),
        ("abort", "media"),
        ("continue", "document"),
        ("continue", "script"),
    ]


def test_http_404_is_permanent_with_status(fake_playwright):
    state = fake_playwright(FakePage(status=404))
    with pytest.raises(FetchError) as exc:
        browser.fetch_rendered("https://example.com/")
    assert exc.value.status_code == 404
    assert state["browser"].closed is True


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_http_statuses(fake_playwright, status):
    fake_playwright(FakePage(status=status))
    with pytest.raises(TransientFetchError):
        browser.fetch_rendered("https://example.com/")


def test_navigation_timeout_is_transient_and_browser_closes(fake_playwright):
    state = fake_playwright(FakePage(goto_error=PlaywrightTimeout("slow")))
    with pytest.raises(TransientFetchError):
        browser.fetch_rendered("https://example.com/")
    assert state["browser"].closed is True


def test_other_playwright_errors_are_permanent(fake_playwright):
    fake_playwright(FakePage(goto_error=PlaywrightError("net::ERR_NAME_NOT_RESOLVED")))
    with pytest.raises(FetchError, match="Browser error"):
        browser.fetch_rendered("https://example.com/")


def test_launch_failure_is_a_fetch_error(fake_playwright):
    fake_playwright(FakePage(), launch_error=PlaywrightError("no chromium"))
    with pytest.raises(FetchError, match="Browser error"):
        browser.fetch_rendered("https://example.com/")
