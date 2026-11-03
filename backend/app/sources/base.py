"""What every source adapter returns, and helpers shared between them.

A source turns a monitored URL into text the pipeline can hash and diff:
`paragraphs` are the lines the chunker and the insight diff work on, `text`
is what the change hash is computed from. The pipeline doesn't know or care
where the text came from.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from app.scraping.extractor import normalize_text


class BrowserRequired(Exception):
    """A plain fetch wasn't enough for this page: retry it with the headless browser."""


@dataclass
class SourceResult:
    url: str  # final URL, after redirects
    text: str
    paragraphs: list[str]
    via: str  # recorded on the snapshot: httpx, browser, telegram, apify:instagram...


class Source(ABC):
    """One way of reading a kind of page. Errors are the fetcher's:
    FetchError (permanent), TransientFetchError (retry later) or BrowserRequired."""

    name: str
    # False when a third party fetches the page for us (it applies its own rules)
    respects_robots: bool = True

    @abstractmethod
    def read(self, url: str) -> SourceResult: ...


# ── posts: social channels ───────────────────────────────────────────────────

@dataclass
class Post:
    day: str  # YYYY-MM-DD, or "" when unknown
    text: str
    link: str

    def line(self) -> str:
        return " · ".join(part for part in (self.day, normalize_text(self.text), self.link) if part)


def posts_result(url: str, posts: list[Post], via: str) -> SourceResult:
    """One line per post, so a new post shows up as one added line."""
    lines = [p.line() for p in posts]
    return SourceResult(url=url, text="\n".join(lines), paragraphs=lines, via=via)


def to_day(value) -> str:
    """YYYY-MM-DD from the date formats platforms use; "" if unrecognised."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        seconds = float(value)
        if seconds > 1e11:  # milliseconds
            seconds /= 1000
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d")
    text = str(value).strip()
    for parse in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
        lambda s: datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y"),  # X / Twitter
    ):
        try:
            return parse(text).astimezone(timezone.utc).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""
