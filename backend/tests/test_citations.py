from app.rag.citations import (
    cited_numbers,
    invalid_numbers,
    strip_invalid,
    uncited_facts,
)


def test_real_and_made_up_numbers_are_told_apart():
    text = "A [1]. B [2][7]. C [0]."
    assert cited_numbers(text, 2) == {1, 2}
    assert invalid_numbers(text, 2) == {0, 7}
    assert strip_invalid(text, 2) == "A [1]. B [2]. C ."


def test_uncited_facts_finds_numbers_without_a_citation():
    text = "Pro fell to $39 [1]. Starter is $19. They seem focused on small teams."
    assert uncited_facts(text) == ["Starter is $19."]


def test_uncited_facts_ignores_list_numbering_and_headings():
    text = "## 2026 changes\n1. Pro got cheaper [1]\n2. Nothing else stands out"
    assert uncited_facts(text) == []


def test_citation_after_the_full_stop_counts():
    assert uncited_facts("Plus moved to €200/year. [1][2]") == []


def test_decimal_points_do_not_split_a_sentence():
    assert uncited_facts("Pro is $39.99/month [1].") == []
