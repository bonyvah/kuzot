import hashlib

from app.scraping.extractor import normalize_text


def content_hash(text: str) -> str:
    """SHA-256 hex digest of normalized text (64 chars, fits last_content_hash)."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def has_changed(previous_hash: str | None, new_hash: str) -> bool:
    """First scrape (no previous hash) counts as a change: we need a baseline."""
    return previous_hash != new_hash