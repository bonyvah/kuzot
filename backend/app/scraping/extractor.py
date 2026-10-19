import re
import unicodedata

import trafilatura

MIN_TEXT_CHARS = 200  # below this, the page is probably a JS shell

_WHITESPACE = re.compile(r"\s+")
_NOSCRIPT = re.compile(
    rb"<noscript\b[^>]*>.*?</noscript\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)

def _run(content: bytes, *, precision: bool) -> str | None:
    return trafilatura.extract(
        content,
        favor_precision=precision,
        favor_recall=not precision,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
    )

def extract_text(content: bytes) -> str | None:
    content = _NOSCRIPT.sub(b"", content)
    text = _run(content, precision=True)
    if is_thin(text):
        recall = _run(content, precision=False)
        if recall and len(recall) > len(text or ""):
            text = recall
    return text


def normalize_text(text: str) -> str:
    """Make equal content compare equal: same unicode form, one-space whitespace."""
    text = unicodedata.normalize("NFKC", text)
    return _WHITESPACE.sub(" ", text).strip()


def is_thin(text: str | None) -> bool:
    """True when extraction found too little: trigger the Playwright fallback."""
    return text is None or len(text) < MIN_TEXT_CHARS

def split_paragraphs(text: str) -> list[str]:
    """Normalized non-empty lines: the units the embedding chunker packs."""
    return [p for p in (normalize_text(line) for line in text.splitlines()) if p]
