"""Read prices out of page text and work out how they changed.

Deterministic on purpose: the numbers an analyst quotes must come from the page,
not from a model's reading of it. Unrecognised text yields no price rather than
a guessed one.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

_CURRENCIES = {
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "₸": "KZT",
    "kzt": "KZT",
    "тг": "KZT",
    "тенге": "KZT",
    "₽": "RUB",
    "rub": "RUB",
    "руб": "RUB",
    "¥": "JPY",
    "jpy": "JPY",
}
_SYMBOL = r"[$€£₸₽¥]"
_CODE = r"(?:USD|EUR|GBP|KZT|RUB|JPY)\b"
_WORD = r"(?:тенге|тг|руб)\.?"
# 1,299.00 / 1 299 / 1.299,00 / 49,99 / 49
_NUMBER = r"\d{1,3}(?:[,.  ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_PRICE = re.compile(
    rf"(?P<pre>{_SYMBOL}|{_CODE})\s?(?P<num_a>{_NUMBER})"
    rf"|(?<![\d.,])(?P<num_b>{_NUMBER})\s?(?P<post>{_SYMBOL}|{_CODE}|{_WORD})",
    re.IGNORECASE,
)
_PERIOD = re.compile(
    r"\s*(?:/|per\b|a\b|в\b)?\s*(?P<unit>month(?:ly)?|mo\b|мес(?:яц)?\b"
    r"|year(?:ly)?|annual(?:ly)?|yr\b|год\b)",
    re.IGNORECASE,
)
_FILLER = re.compile(
    r"^(?:from|starting at|starts at|only|just|от)(?:\s+|$)|\s+(?:from|от)$", re.I
)
_TRIM = " \t:-–—|•*·,#"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
    period: Literal["month", "year"] | None = None


@dataclass(frozen=True)
class PriceMention:
    label: str  # plan or product the price belongs to; "" when the page doesn't say
    money: Money
    raw: str  # the line it was read from


@dataclass(frozen=True)
class PriceChange:
    label: str
    direction: Literal["increase", "decrease", "added", "removed", "terms_changed"]
    old: Money | None
    new: Money | None
    change_pct: float | None  # only when currency and period both stayed the same


def _parse_number(text: str) -> Decimal | None:
    digits = text.replace(" ", "").replace(" ", "")
    last_sep = max(digits.rfind(","), digits.rfind("."))
    # a final separator followed by 1-2 digits marks decimals; 3 means thousands
    if last_sep != -1 and len(digits) - last_sep - 1 in (1, 2):
        whole = digits[:last_sep].replace(",", "").replace(".", "")
        digits = f"{whole}.{digits[last_sep + 1 :]}"
    else:
        digits = digits.replace(",", "").replace(".", "")
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def _period(after: str) -> tuple[Literal["month", "year"] | None, int]:
    match = _PERIOD.match(after)
    if not match:
        return None, 0
    unit = match["unit"].lower()
    period = "month" if unit.startswith(("mo", "мес")) else "year"
    return period, match.end()


def _clean_label(text: str) -> str:
    label = _FILLER.sub("", text.strip(_TRIM)).strip(_TRIM)
    return " ".join(label.split())


def parse_line(line: str) -> list[tuple[str, Money]]:
    """Every price on a line, each with the label the line itself gives it."""
    found: list[tuple[Money, int, int]] = []
    for match in _PRICE.finditer(line):
        symbol = (match["pre"] or match["post"]).lower().rstrip(".")
        currency = _CURRENCIES.get(symbol)
        amount = _parse_number(match["num_a"] or match["num_b"])
        if currency is None or amount is None:
            continue
        period, length = _period(line[match.end() :])
        found.append(
            (Money(amount, currency, period), match.start(), match.end() + length)
        )
    if not found:
        return []
    label = _clean_label(line[: found[0][1]]) or _clean_label(line[found[-1][2] :])
    return [(label, money) for money, _, _ in found]


def extract_prices(lines: Iterable[str]) -> list[PriceMention]:
    """Prices in reading order; a bare price takes the line above it as its label."""
    mentions: list[PriceMention] = []
    heading = ""
    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            heading = _clean_label(line) or heading
            continue
        mentions += [
            PriceMention(label or heading, money, line.strip())
            for label, money in parsed
        ]
    return mentions


def _key(label: str) -> str:
    return label.casefold()


def _describe(old: Money, new: Money, label: str) -> PriceChange | None:
    if old == new:
        return None
    if old.currency != new.currency or old.period != new.period:
        return PriceChange(label, "terms_changed", old, new, None)
    pct = None
    if old.amount:
        pct = round(float((new.amount - old.amount) / old.amount * 100), 1)
    direction = "increase" if new.amount > old.amount else "decrease"
    return PriceChange(label, direction, old, new, pct)


def _hunk_sides(hunk: list[dict]) -> tuple[list[PriceMention], list[PriceMention]]:
    """Each side reads like its own page: context lines plus its own changes."""
    old_lines = [line["text"] for line in hunk if line["op"] != "added"]
    new_lines = [line["text"] for line in hunk if line["op"] != "removed"]
    changed = {line["text"] for line in hunk if line["op"] != "context"}
    old = [
        m for m in extract_prices(old_lines) if m.raw in {t.strip() for t in changed}
    ]
    new = [
        m for m in extract_prices(new_lines) if m.raw in {t.strip() for t in changed}
    ]
    return old, new


def diff_prices(hunks: list[list[dict]]) -> list[PriceChange]:
    """What happened to each price in an insight's line diff.

    Prices pair up by label and period, then label, then position. Anything left
    was added or removed. A line that moved with the same price is not a change.
    """
    changes: list[PriceChange] = []
    for hunk in hunks:
        old, new = _hunk_sides(hunk)
        matchers = (
            lambda a, b: (
                _key(a.label) == _key(b.label) and a.money.period == b.money.period
            ),
            lambda a, b: _key(a.label) == _key(b.label),
        )
        for same in matchers:
            for a in list(old):
                b = next((m for m in new if same(a, m)), None)
                if b is None:
                    continue
                old.remove(a)
                new.remove(b)
                change = _describe(a.money, b.money, a.label or b.label)
                if change:
                    changes.append(change)
        # relabelled plans: only safe to pair by position when the counts agree
        if len(old) == len(new):
            for a, b in zip(old, new, strict=True):
                change = _describe(a.money, b.money, b.label or a.label)
                if change:
                    changes.append(change)
            continue
        changes += [PriceChange(m.label, "removed", m.money, None, None) for m in old]
        changes += [PriceChange(m.label, "added", None, m.money, None) for m in new]
    return changes
