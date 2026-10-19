import hashlib
import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 1500
MIN_CHUNK_CHARS = 400
BOUNDARY_MODULUS = 3  # ~1 in 3 units may end a chunk once it is past the minimum

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    text: str
    hash: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hard_split(text: str) -> list[str]:
    """Word-wrap a run-on unit (no sentence breaks) into MAX_CHUNK_CHARS pieces."""
    pieces, current = [], ""
    for word in text.split(" "):
        if current and len(current) + 1 + len(word) > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def _fit(units: list[str]) -> list[str]:
    """Break oversized units into sentences, then words, so each fits a chunk."""
    fitted = []
    for unit in units:
        if len(unit) <= MAX_CHUNK_CHARS:
            fitted.append(unit)
            continue
        for sentence in _SENTENCE_END.split(unit):
            if len(sentence) <= MAX_CHUNK_CHARS:
                fitted.append(sentence)
            else:
                fitted.extend(_hard_split(sentence))
    return fitted


def _is_boundary(unit: str) -> bool:
    # content-defined: depends on the unit itself, not its position on the page,
    # so an edit only reshapes nearby chunks and the rest keep their hashes
    return int(_sha256(unit)[:8], 16) % BOUNDARY_MODULUS == 0


def chunk_units(units: list[str]) -> list[Chunk]:
    """Pack paragraphs into chunks whose boundaries survive edits elsewhere."""
    texts, current = [], []
    size = 0
    for unit in _fit([u for u in units if u]):
        if current and size + 1 + len(unit) > MAX_CHUNK_CHARS:
            texts.append("\n".join(current))
            current, size = [], 0
        current.append(unit)
        size += len(unit) + (1 if size else 0)
        if size >= MIN_CHUNK_CHARS and _is_boundary(unit):
            texts.append("\n".join(current))
            current, size = [], 0
    if current:
        texts.append("\n".join(current))

    seen, chunks = set(), []
    for text in texts:
        digest = _sha256(text)
        if digest not in seen:  # repeated blocks (e.g. two CTAs) embed once
            seen.add(digest)
            chunks.append(Chunk(text=text, hash=digest))
    return chunks


def snapshot_units(snapshot: dict) -> list[str]:
    """Paragraphs when the scraper stored them; sentences for older snapshots."""
    paragraphs = snapshot.get("paragraphs")
    if paragraphs:
        return paragraphs
    return _SENTENCE_END.split(snapshot.get("text") or "")
