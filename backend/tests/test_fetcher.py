import httpx
import pytest
from tenacity import wait_none

from app.scraping import fetcher
from app.scraping.fetcher import (
    FetchError,
    TransientFetchError,
    fetch_html,
)


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(fetch_html.retry, "wait", wait_none())


def use_handler(monkeypatch, handler):
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(fetcher.httpx, "Client", factory)


def html_response(body=b"<html>ok</html>", **kw):
    return httpx.Response(
        200, content=body, headers={"content-type": "text/html; charset=utf-8"}, **kw
    )


def test_success_returns_bytes_and_final_url(monkeypatch):
    use_handler(monkeypatch, lambda req: html_response(b"<html>privet</html>"))
    result = fetch_html("https://example.com/")
    assert result.status_code == 200
    assert result.content == b"<html>privet</html>"
    assert result.url == "https://example.com/"


def test_follows_redirects(monkeypatch):
    def handler(req):
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://example.com/new"})
        return html_response()

    use_handler(monkeypatch, handler)
    assert fetch_html("https://example.com/old").url == "https://example.com/new"


def test_sends_language_and_user_agent_headers(monkeypatch):
    seen = {}

    def handler(req):
        seen.update(req.headers)
        return html_response()

    use_handler(monkeypatch, handler)
    fetch_html("https://example.com/")
    assert "ru" in seen["accept-language"]
    assert "Mozilla" in seen["user-agent"]


@pytest.mark.parametrize("status", [403, 404])
def test_client_errors_are_permanent_and_not_retried(monkeypatch, status):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(status)

    use_handler(monkeypatch, handler)
    with pytest.raises(FetchError) as exc:
        fetch_html("https://example.com/")
    assert exc.value.status_code == status
    assert len(calls) == 1


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_statuses_retry_three_times_then_raise(monkeypatch, status):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(status)

    use_handler(monkeypatch, handler)
    with pytest.raises(TransientFetchError):
        fetch_html("https://example.com/")
    assert len(calls) == 3


def test_recovers_after_transient_failure(monkeypatch):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else html_response()

    use_handler(monkeypatch, handler)
    assert fetch_html("https://example.com/").status_code == 200
    assert len(calls) == 3


def test_timeout_is_transient(monkeypatch):
    def handler(req):
        raise httpx.ConnectTimeout("slow", request=req)

    use_handler(monkeypatch, handler)
    with pytest.raises(TransientFetchError):
        fetch_html("https://example.com/")


def test_network_error_is_transient(monkeypatch):
    def handler(req):
        raise httpx.ConnectError("down", request=req)

    use_handler(monkeypatch, handler)
    with pytest.raises(TransientFetchError):
        fetch_html("https://example.com/")


def test_non_html_is_rejected(monkeypatch):
    use_handler(
        monkeypatch,
        lambda req: httpx.Response(
            200, content=b"%PDF", headers={"content-type": "application/pdf"}
        ),
    )
    with pytest.raises(FetchError, match="Not HTML"):
        fetch_html("https://example.com/file.pdf")


def test_oversized_page_is_rejected(monkeypatch):
    monkeypatch.setattr(fetcher, "MAX_BYTES", 10)
    use_handler(monkeypatch, lambda req: html_response(b"x" * 100))
    with pytest.raises(FetchError, match="too large"):
        fetch_html("https://example.com/")
