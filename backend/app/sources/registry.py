"""Which source reads which kind of page. Add a platform by adding a Source here."""

from app.models.monitored_url import URLType
from app.sources.apify import FacebookSource, InstagramSource, XSource
from app.sources.base import Source
from app.sources.telegram import TelegramSource
from app.sources.web import BrowserSource, HttpSource

_BY_TYPE: dict[URLType, Source] = {
    URLType.TELEGRAM: TelegramSource(),
    URLType.INSTAGRAM: InstagramSource(),
    URLType.FACEBOOK: FacebookSource(),
    URLType.X: XSource(),
}
_HTTP = HttpSource()
_BROWSER = BrowserSource()


def source_for(url_type: URLType, *, use_browser: bool = False) -> Source:
    """The platform's own source, else the web: plain fetch, or the browser on retry."""
    return _BY_TYPE.get(url_type) or (_BROWSER if use_browser else _HTTP)
