"""Candidate pages for a competitor: links on its site, sitemap entries and
known handles, each with a page type guessed from the URL."""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.models.monitored_url import URLType

# hosts that identify a social channel; anything else on another host is skipped
SOCIAL_HOSTS: dict[str, tuple[URLType, str | None]] = {
    "instagram.com": (URLType.INSTAGRAM, None),
    "t.me": (URLType.TELEGRAM, None),
    "telegram.me": (URLType.TELEGRAM, None),
    "facebook.com": (URLType.FACEBOOK, None),
    "fb.com": (URLType.FACEBOOK, None),
    "x.com": (URLType.X, None),
    "twitter.com": (URLType.X, None),
    "linkedin.com": (URLType.OTHER, "LinkedIn"),
    "youtube.com": (URLType.OTHER, "YouTube"),
    "tiktok.com": (URLType.OTHER, "TikTok"),
}

# path hints for pages on the competitor's own site
PATH_TYPES: list[tuple[re.Pattern, URLType]] = [
    (re.compile(r"/(pricing|prices|plans|tariffs?|price)(/|$|\.)", re.I), URLType.PRICING),
    # shops: catalogs and delivery fees are where prices live
    (re.compile(r"/(catalog|catalogue|shop|store|products|delivery|shipping)(/|$|\.)", re.I), URLType.PRICING),
    (re.compile(r"/(changelog|release-notes|releases|whats-new|updates)(/|$|\.)", re.I), URLType.CHANGELOG),
    (re.compile(r"/(blog|news|articles|posts|journal)(/|$|\.)", re.I), URLType.BLOG),
    (re.compile(r"/(docs|documentation|help|guide|kb|support)(/|$|\.)", re.I), URLType.DOCS),
]

# site pages never worth monitoring
_SKIP_PATH = re.compile(
    r"/(cart|basket|checkout|order|orders|login|log-in|signin|sign-in|signup|sign-up|register|account|"
    r"privacy|terms|legal|cookies?|careers|jobs|vacancies)(/|$|\.)",
    re.I,
)

# social paths that are never a channel page
_NOT_A_CHANNEL = re.compile(r"^/(share|sharer|intent|login|signup|explore|hashtag|p/|reel/|status/|watch)", re.I)


@dataclass
class Candidate:
    url: str
    url_type: URLType
    label: str | None = None
    # where it was found: site, sitemap, hint or search; plus anchor text / title
    sources: set[str] = field(default_factory=set)
    text: str = ""


def _host(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.").removeprefix("m.")


def normalize(url: str) -> str | None:
    """http(s) URL without fragment or tracking query; None if not a web URL."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    query = "&".join(q for q in parts.query.split("&") if q and not q.lower().startswith(("utm_", "ref=", "fbclid")))
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, query, ""))


def classify(url: str, site_host: str) -> tuple[URLType, str | None] | None:
    """Page type for a URL, or None when it's neither on the site nor a known channel."""
    host = _host(url)
    for social, kind in SOCIAL_HOSTS.items():
        if host == social or host.endswith("." + social):
            path = urlsplit(url).path
            if path in ("", "/") or _NOT_A_CHANNEL.match(path):
                return None
            return kind
    if host != site_host and not host.endswith("." + site_host):
        return None
    path = urlsplit(url).path
    if _SKIP_PATH.search(path):
        return None
    if host.startswith("docs.") or host.startswith("help."):
        return URLType.DOCS, None
    if host.startswith("blog."):
        return URLType.BLOG, None
    if path in ("", "/"):
        return URLType.HOMEPAGE, None
    for pattern, kind in PATH_TYPES:
        if pattern.search(path):
            return kind, None
    return URLType.OTHER, None


def telegram_web(url: str) -> str:
    """Public channels are readable at t.me/s/<name>, which is what gets scraped."""
    parts = urlsplit(url)
    name = parts.path.strip("/").split("/")[-1]
    return f"https://t.me/s/{name}" if name else url


def from_html(html: bytes | str, base_url: str) -> list[tuple[str, str]]:
    """(absolute url, anchor text) for every link on a page."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.find_all("a", href=True):
        url = normalize(urljoin(base_url, a["href"]))
        if url:
            out.append((url, " ".join(a.get_text(" ").split())[:80]))
    return out


def from_sitemap(xml: bytes | str) -> list[str]:
    return [loc.strip() for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml if isinstance(xml, str) else xml.decode("utf-8", "ignore"))]


HANDLE_URLS = {
    URLType.INSTAGRAM: "https://instagram.com/{}",
    URLType.TELEGRAM: "https://t.me/s/{}",
    URLType.FACEBOOK: "https://facebook.com/{}",
    URLType.X: "https://x.com/{}",
}


def from_hint(kind: URLType, value: str) -> str | None:
    """A channel the user typed: a full URL, or a bare handle like @acme."""
    value = value.strip()
    if not value:
        return None
    if "://" in value or "." in value.split("/")[0]:
        return normalize(value if "://" in value else f"https://{value}")
    template = HANDLE_URLS.get(kind)
    return template.format(value.lstrip("@")) if template else None
