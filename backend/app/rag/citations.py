"""Check the [n] source markers in generated text against the real sources."""

import re

_CITATION = re.compile(r"\[(\d+)\]")
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")
# a citation after the full stop still belongs to that sentence
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?!\[\d+\])")
_FACT = re.compile(r"[\d$€£₸₽¥]")


def cited_numbers(text: str, source_count: int) -> set[int]:
    """Numbers the text cites that are real sources (1-based)."""
    return {int(n) for n in _CITATION.findall(text) if 1 <= int(n) <= source_count}


def invalid_numbers(text: str, source_count: int) -> set[int]:
    """Numbers the text cites that no source has: made up by the model."""
    return {int(n) for n in _CITATION.findall(text) if not 1 <= int(n) <= source_count}


def strip_invalid(text: str, source_count: int) -> str:
    def keep_real(match: re.Match[str]) -> str:
        return match[0] if 1 <= int(match[1]) <= source_count else ""

    return _CITATION.sub(keep_real, text)


def uncited_facts(text: str) -> list[str]:
    """Sentences stating a number, price or date without citing anything."""
    uncited = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        body = _LIST_MARKER.sub("", line)
        for sentence in _SENTENCE_END.split(body):
            if _FACT.search(sentence) and not _CITATION.search(sentence):
                uncited.append(sentence.strip())
    return uncited
