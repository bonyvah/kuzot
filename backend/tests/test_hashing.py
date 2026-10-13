from app.scraping.hashing import content_hash, has_changed


def test_hash_is_64_hex_chars():
    h = content_hash("hello")
    assert len(h) == 64
    int(h, 16)


def test_whitespace_differences_do_not_change_hash():
    assert content_hash("Plan: Pro   $20 / month") == content_hash(
        "Plan:\n  Pro $20 /  month"
    )


def test_unicode_forms_do_not_change_hash():
    composed = "café"
    decomposed = "café"
    nbsp = "a b"
    assert content_hash(composed) == content_hash(decomposed)
    assert content_hash(nbsp) == content_hash("a b")


def test_real_content_change_changes_hash():
    assert content_hash("Pro $20 / month") != content_hash("Pro $25 / month")


def test_cyrillic_is_stable():
    assert content_hash("Привет  мир") == content_hash("Привет мир")
    assert content_hash("Привет мир") != content_hash("Привет мира")


def test_has_changed():
    h = content_hash("a")
    assert has_changed(None, h) is True
    assert has_changed(h, h) is False
    assert has_changed(h, content_hash("b")) is True
