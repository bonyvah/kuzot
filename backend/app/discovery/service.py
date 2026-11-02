"""Find a competitor's useful pages: its site, sitemap, user hints and web search."""

from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from app.discovery import search
from app.discovery.links import (
    Candidate,
    classify,
    from_hint,
    from_html,
    from_sitemap,
    normalize,
    telegram_web,
)
from app.discovery.select import pick
from app.models.monitored_url import URLType
from app.scraping.fetcher import USER_AGENT, FetchError, TransientFetchError, fetch_html
from app.workers.pipeline import robots_allows

MAX_CANDIDATES = 150
MAX_SITEMAP_URLS = 300
MAX_SEARCHES = 4

CHANNEL_WORDS = {
    URLType.INSTAGRAM: "Instagram",
    URLType.TELEGRAM: "Telegram channel",
    URLType.FACEBOOK: "Facebook page",
    URLType.X: "X Twitter",
}

# order pages are shown in, most useful first
TYPE_ORDER = [URLType.HOMEPAGE, URLType.PRICING, URLType.CHANGELOG, URLType.BLOG, URLType.DOCS,
              URLType.TELEGRAM, URLType.INSTAGRAM, URLType.FACEBOOK, URLType.X, URLType.OTHER]


@dataclass
class Hint:
    url_type: URLType
    value: str = ""  # a handle or URL; empty means "look for one"
    label: str | None = None


@dataclass
class Found:
    url: str
    url_type: URLType
    label: str | None
    reason: str
    source: str


@dataclass
class Discovery:
    pages: list[Found]
    notes: list[str] = field(default_factory=list)


def _site_host(website: str | None) -> str:
    return (urlsplit(website).hostname or "").removeprefix("www.") if website else ""


def discover(
    *,
    name: str,
    website: str | None,
    description: str | None = None,
    notes: str | None = None,
    hints: list[Hint] | None = None,
    looking_for: str | None = None,
    exclude: set[str] | None = None,
) -> Discovery:
    """Candidate pages for a competitor, typed and explained, ready for review.

    `looking_for` narrows it to one kind of page ("their pricing page");
    `exclude` drops URLs that are already monitored.
    """
    hints = hints or []
    exclude = {normalize(u) or u for u in (exclude or set())}
    result_notes: list[str] = []
    site = normalize(website) if website else None
    host = _site_host(site)
    found: dict[str, Candidate] = {}

    def add(url: str | None, source: str, text: str = "", kind=None) -> None:
        url = normalize(url) if url else None
        if not url:
            return
        typed = kind or classify(url, host)
        if typed is None:
            return
        url_type, label = typed
        if url_type == URLType.TELEGRAM:
            url = telegram_web(url)
        c = found.setdefault(url, Candidate(url=url, url_type=url_type, label=label))
        c.sources.add(source)
        if text and not c.text:
            c.text = text

    # 1. the website itself: its links and sitemap
    if site:
        add(site, "site", "Homepage", (URLType.HOMEPAGE, None))
        if robots_allows(site):
            try:
                page = fetch_html(site)
                for url, text in from_html(page.content, page.url):
                    add(url, "site", text)
            except (FetchError, TransientFetchError) as exc:
                result_notes.append(f"Couldn't read {site}: {exc}")
        else:
            result_notes.append(f"{host} asks bots not to read its homepage")
        try:
            sitemap = httpx.get(f"{urlsplit(site).scheme}://{urlsplit(site).netloc}/sitemap.xml",
                                headers={"User-Agent": USER_AGENT}, timeout=10, follow_redirects=True)
            if sitemap.status_code == 200:
                for url in from_sitemap(sitemap.text)[:MAX_SITEMAP_URLS]:
                    add(url, "sitemap")
        except httpx.HTTPError:
            pass

    # 2. channels the user told us about
    wanted: list[URLType] = []
    for hint in hints:
        if not hint.value:
            wanted.append(hint.url_type)
            continue
        url = from_hint(hint.url_type, hint.value)
        if not url:
            continue
        if hint.url_type == URLType.HOMEPAGE:
            # "another web page": typed by its own address (pricing, blog...)
            kind = classify(url, _site_host(url))
        elif hint.url_type == URLType.OTHER:
            kind = (URLType.OTHER, hint.label or _site_host(url))
        else:
            kind = (hint.url_type, None)
        add(url, "hint", hint.label or "", kind)

    # 3. web search for what the site doesn't link
    queries = [f"{name} {looking_for}"] if looking_for else []
    queries += [f"{name} {CHANNEL_WORDS[t]}" for t in wanted if t in CHANNEL_WORDS]
    if not site:
        queries.insert(0, f"{name} official website")
    if queries:
        if search.enabled():
            for query in queries[:MAX_SEARCHES]:
                try:
                    for r in search.search(query):
                        add(r["url"], "search", r["title"])
                except httpx.HTTPError as exc:
                    result_notes.append(f"Web search failed: {exc}")
                    break
        else:
            result_notes.append("Web search is off (no TAVILY_API_KEY), so only the website was checked")

    # 4. pick and type the useful ones
    candidates = [c for url, c in found.items() if url not in exclude]
    candidates.sort(key=lambda c: ("hint" not in c.sources, c.url_type == URLType.OTHER and not c.label, len(c.url)))
    candidates = candidates[:MAX_CANDIDATES]
    picked = pick(candidates, name=name, website=site, description=description, notes=notes, looking_for=looking_for)
    if picked is None:
        result_notes.append("AI selection is unavailable; showing pages matched by their address")
        picked = [(c, "Matched by address") for c in candidates if _obvious(c)]

    # what the user explicitly gave is always offered
    chosen = {c.url for c, _ in picked}
    picked += [(c, "You added this channel") for c in candidates if "hint" in c.sources and c.url not in chosen]

    pages = [
        Found(url=c.url, url_type=c.url_type, label=c.label, reason=reason,
              source="hint" if "hint" in c.sources else "search" if c.sources == {"search"} else "site")
        for c, reason in picked
    ]
    pages.sort(key=lambda p: TYPE_ORDER.index(p.url_type))
    return Discovery(pages=pages, notes=result_notes)


def _obvious(c: Candidate) -> bool:
    """Without the model: keep typed pages and channels, skip arbitrary site pages."""
    return c.url_type != URLType.OTHER or c.label is not None
