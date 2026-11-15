"""The evals are only worth something if their assertions can fail."""

from evals.asserts import citations_valid, price_changes_match


def _answer(text, *sources, valid=True):
    return {
        "answer": text,
        "citations_valid": valid,
        "sources": [
            {"number": i, "text": source} for i, source in enumerate(sources, start=1)
        ],
    }


def test_good_answer_passes():
    output = _answer("Pro is $39/month [1].", "Pro $39/month")
    assert citations_valid(output, {})["pass"] is True


def test_citation_with_no_source_fails():
    output = _answer("Pro is $39/month [9].", "Pro $39/month")
    assert citations_valid(output, {})["pass"] is False


def test_amount_missing_from_cited_source_fails():
    output = _answer("Pro is $45/month [1].", "Pro $39/month")
    assert "45" in citations_valid(output, {})["reason"]


def test_amount_only_in_an_uncited_source_fails():
    output = _answer("Pro is $39/month [1].", "Starter $19", "Pro $39/month")
    assert citations_valid(output, {})["pass"] is False


def test_difference_of_cited_prices_is_allowed():
    output = _answer("Up $6, from $19 to $25 [1].", "$19 to $25")
    assert citations_valid(output, {})["pass"] is True


def test_wrong_price_change_fails():
    output = {
        "changes": [
            {
                "label": "Pro",
                "direction": "decrease",
                "change_pct": -10.0,
                "old": {"amount": 49.0},
                "new": {"amount": 39.0},
            }
        ]
    }
    expect = [
        {
            "label": "Pro",
            "direction": "decrease",
            "change_pct": -20.4,
            "old": 49.0,
            "new": 39.0,
        }
    ]
    assert price_changes_match(output, {"vars": {"expect": expect}})["pass"] is False
