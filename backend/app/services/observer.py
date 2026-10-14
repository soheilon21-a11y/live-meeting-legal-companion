from app.services import retrieval, session_store

MIN_EXCERPT_CHARS = 20
MAX_EXCERPT_CHARS = 2000
TOP_K = 3


def _build_observation(excerpt: str, passage: dict) -> dict:
    snippet = passage["text"].strip()
    return {
        "issue_question": (
            f"Does this part of the discussion relate to the contract passage "
            f"“{snippet[:160]}”?"
        ),
        "evidence_status": "supported",
        "suggested_question": (
            f"“{snippet[:140]}” — does this apply to the point just raised?"
        ),
        "transcript_excerpt": excerpt,
    }


def check_recent_transcript(
    session_id: str,
    since_index: int,
    document_id: str,
) -> dict:
    entries = [
        entry
        for entry in session_store.get_transcript(session_id)
        if entry.get("chunk_index", 0) > since_index
    ]
    if not entries:
        return {"observations": [], "last_index": since_index}

    last_index = max(entry.get("chunk_index", since_index) for entry in entries)

    excerpt = " ".join(entry.get("text", "") for entry in entries).strip()
    excerpt = excerpt[:MAX_EXCERPT_CHARS]
    if len(excerpt) < MIN_EXCERPT_CHARS:
        return {"observations": [], "last_index": last_index}

    passages = retrieval.retrieve(document_id, excerpt, k=TOP_K)
    if not passages:
        return {"observations": [], "last_index": last_index}

    return {
        "observations": [_build_observation(excerpt, passages[0])],
        "last_index": last_index,
    }
