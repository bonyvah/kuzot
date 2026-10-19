from app.embedding.chunking import (
    MAX_CHUNK_CHARS,
    chunk_units,
    snapshot_units,
)


def paragraphs(n: int, tag: str = "p") -> list[str]:
    return [
        f"Paragraph {tag}{i}: the plan includes feature {i} and costs {i * 3} dollars."
        for i in range(n)
    ]


def test_chunks_respect_max_size():
    chunks = chunk_units(paragraphs(200))
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)


def test_all_text_is_kept_in_order():
    units = paragraphs(50)
    chunks = chunk_units(units)
    assert "\n".join(c.text for c in chunks) == "\n".join(units)


def test_same_input_same_hashes():
    assert chunk_units(paragraphs(80)) == chunk_units(paragraphs(80))


def test_edit_in_the_middle_keeps_most_chunks():
    before = paragraphs(200)
    after = (
        before[:100]
        + ["Brand new paragraph announcing an Enterprise tier."]
        + before[100:]
    )
    old = {c.hash for c in chunk_units(before)}
    new = {c.hash for c in chunk_units(after)}
    # content-defined boundaries: only the chunks around the insert change
    assert len(new - old) <= 2
    assert len(old - new) <= 2


def test_oversized_paragraph_is_split_by_sentences():
    long = " ".join(f"Sentence number {i} talks about pricing." for i in range(200))
    chunks = chunk_units([long])
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)


def test_run_on_text_without_sentences_is_word_wrapped():
    chunks = chunk_units(["word " * 1000])
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)


def test_duplicate_chunks_are_dropped():
    block = "Sign up today and get the first month free. " * 12
    chunks = chunk_units([block] * 6)
    assert len({c.hash for c in chunks}) == len(chunks)


def test_snapshot_units_prefers_paragraphs():
    assert snapshot_units({"paragraphs": ["a", "b"], "text": "a b"}) == ["a", "b"]


def test_snapshot_units_falls_back_to_sentences():
    units = snapshot_units({"text": "First one. Second one! Third?"})
    assert units == ["First one.", "Second one!", "Third?"]
