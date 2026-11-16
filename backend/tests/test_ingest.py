from app.services.ingest import chunk_text


def test_chunks_do_not_start_mid_word():
    # The first chunk covers 600 characters, splitting the long run of "A"s
    # right before "extraordinary". The overlapping next chunk must start at a
    # word boundary instead of a fragment such as "ordinary clause".
    text = "A" * 590 + " extraordinary clause follows here " + "B" * 100
    chunks = chunk_text(text, size=600, overlap=120)
    assert chunks[0].startswith("A")
    assert chunks[1].startswith("extraordinary clause")


def test_chunking_preserves_text_coverage():
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, size=120, overlap=30)
    assert len(chunks) > 1
    # Every non-overlapping source token must appear in some chunk; the word
    # boundary alignment must not drop text between chunks.
    joined = " ".join(chunks)
    for i in (0, 1, 199, 399):
        assert f"word{i}" in joined
