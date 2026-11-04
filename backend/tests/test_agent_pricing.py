from decimal import Decimal

import pytest

from app.agent.pricing import Money, diff_prices, extract_prices, parse_line


@pytest.mark.parametrize(
    ("line", "label", "amount", "currency", "period"),
    [
        ("Pro plan: $49/month", "Pro plan", "49", "USD", "month"),
        ("$1,299.00 per year", "", "1299.00", "USD", "year"),
        ("Business — 1 299 ₸ / мес", "Business", "1299", "KZT", "month"),
        ("Starter 49,99 € a month", "Starter", "49.99", "EUR", "month"),
        ("от 15 000 тг в месяц", "", "15000", "KZT", "month"),
        ("USD 30 monthly", "", "30", "USD", "month"),
        ("Team 1.299,00 EUR/yr", "Team", "1299.00", "EUR", "year"),
        ("Add-on: £5", "Add-on", "5", "GBP", None),
    ],
)
def test_parse_line_reads_price(line, label, amount, currency, period):
    assert parse_line(line) == [(label, Money(Decimal(amount), currency, period))]


@pytest.mark.parametrize(
    "line",
    ["Save 20% with 3 seats", "Version 2.5 released 2026", "Contact sales", ""],
)
def test_parse_line_ignores_numbers_that_are_not_prices(line):
    assert parse_line(line) == []


def test_two_prices_on_one_line_share_the_label():
    assert [label for label, _ in parse_line("Pro $20/month or $200/year")] == [
        "Pro",
        "Pro",
    ]


def test_bare_price_takes_the_heading_above():
    mentions = extract_prices(["Starter", "$19/month", "Pro", "$39/month"])
    assert [(m.label, m.money.amount) for m in mentions] == [
        ("Starter", Decimal(19)),
        ("Pro", Decimal(39)),
    ]


def _hunk(*lines):
    return [{"op": op, "text": text} for op, text in lines]


def test_diff_reads_a_cut_using_context_as_label():
    [change] = diff_prices(
        [_hunk(("context", "Pro"), ("removed", "$49/month"), ("added", "$39/month"))]
    )
    assert change.label == "Pro"
    assert change.direction == "decrease"
    assert change.change_pct == -20.4


def test_diff_pairs_by_label_not_position():
    changes = diff_prices(
        [
            _hunk(
                ("removed", "Starter: $19/month"),
                ("removed", "Pro: $49/month"),
                ("added", "Pro: $59/month"),
                ("added", "Starter: $19/month"),
            )
        ]
    )
    assert [(c.label, c.direction) for c in changes] == [("Pro", "increase")]


def test_diff_new_period_or_currency_has_no_percentage():
    [change] = diff_prices(
        [_hunk(("removed", "Plus: €20/month"), ("added", "Plus: €200/year"))]
    )
    assert change.direction == "terms_changed"
    assert change.change_pct is None


def test_diff_reports_added_and_removed_plans():
    added = diff_prices([_hunk(("context", "Pro"), ("added", "Team plan: $99/month"))])
    assert [(c.label, c.direction) for c in added] == [("Team plan", "added")]
    removed = diff_prices([_hunk(("removed", "Legacy: $5/month"))])
    assert [(c.label, c.direction) for c in removed] == [("Legacy", "removed")]


def test_diff_ignores_context_prices_and_text_edits():
    hunk = _hunk(
        ("context", "Business: $120/month"),
        ("removed", "Great for teams"),
        ("added", "Great for big teams"),
    )
    assert diff_prices([hunk]) == []


def test_diff_ignores_price_that_only_moved():
    hunk = _hunk(("removed", "Pro: $49/month"), ("added", "Pro: $49/month"))
    assert diff_prices([hunk]) == []
