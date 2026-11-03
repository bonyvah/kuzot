"""Source adapters: every platform plugs into the same scrape pipeline.

    source = source_for(url_type, use_browser=...)
    result = source.read(url)   # -> SourceResult(url, text, paragraphs, via)

See registry.py to add a platform.
"""

from app.sources.base import BrowserRequired, Source, SourceResult
from app.sources.registry import source_for

__all__ = ["BrowserRequired", "Source", "SourceResult", "source_for"]
