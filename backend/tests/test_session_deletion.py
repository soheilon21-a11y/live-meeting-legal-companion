import threading

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import chroma_store, consent_store, observation_store, session_store
from main import app

client = TestClient(app)


def _upload(name: str, text: str):
    return client.post(
        "/api/live/upload",
        files={"file": (name, text.encode("utf-8"), "text/plain")},
    )


def _collection_exists(session_id: str) -> bool:
    try:
        chroma_store.get(session_id)
        return True
    except Exception:
        return False


def _setup_session_with_artifacts() -> str:
    """Create a session with every artifact type and return its id."""
    resp = _upload("a.txt", "Alpha clause about payment and delivery terms.")
    doc_id = resp.json()["session_id"]
    consent_store.record_consent(doc_id, "DE", ["Alice"], True)
    audio_dir = settings.DATA_DIR / "audio" / doc_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "chunk_0.webm").write_bytes(b"x" * 100)
    observation_store.add_observation(
        doc_id,
        {
            "issue_question": "Does this relate to the clause?",
            "evidence_status": "supported",
            "transcript_excerpt": "an excerpt",
        },
    )
    assert session_store.load_session(doc_id) is not None
    assert _collection_exists(doc_id)
    return doc_id


def _assert_all_gone(doc_id: str) -> None:
    assert session_store.load_session(doc_id) is None
    assert not (settings.DATA_DIR / "audio" / doc_id).exists()
    assert not (settings.DATA_DIR / "observations" / f"{doc_id}.json").exists()
    assert consent_store.get_consents(doc_id) == []
    assert not _collection_exists(doc_id)


def test_delete_removes_all_session_artifacts_and_preserves_others():
    doc_a = _setup_session_with_artifacts()

    # Session B: independent session.
    rb = _upload("b.txt", "Beta clause about liability and termination.")
    doc_b = rb.json()["session_id"]
    consent_store.record_consent(doc_b, "DE", ["Bob"], True)

    resp = client.delete(f"/api/live/session/{doc_a}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "session_id": doc_a}

    # A is fully gone.
    _assert_all_gone(doc_a)

    # B is fully intact.
    assert session_store.load_session(doc_b) is not None
    assert consent_store.get_consents(doc_b)
    assert _collection_exists(doc_b)


def test_delete_rejects_unsafe_session_ids():
    for bad in ["..", "../etc", "a/b", "a\\b", "..\\..\\x", "a.b", "x:y", ""]:
        assert session_store.valid_session_id(bad) is False
        with pytest.raises(ValueError):
            session_store.delete_session(bad)

    for good in ["abc123", "a" * 32, "s1", "race-appends"]:
        assert session_store.valid_session_id(good) is True


def test_delete_endpoint_rejects_invalid_id_with_400():
    resp = client.delete("/api/live/session/a.b")
    assert resp.status_code == 400


def test_delete_is_idempotent():
    sid = client.post("/api/live/session").json()["session_id"]
    assert client.delete(f"/api/live/session/{sid}").status_code == 200
    # Second delete: session already gone -> 404, no crash, no corruption.
    assert client.delete(f"/api/live/session/{sid}").status_code == 404


def test_chroma_delete_treats_exact_missing_collection_value_error_as_gone(monkeypatch):
    """ChromaDB 0.5.x signals a missing collection with ValueError, not NotFoundError."""
    sid = "missing-collection"
    expected = chroma_store.collection_name(sid)

    class FakeClient:
        def delete_collection(self, name):
            assert name == expected
            raise ValueError(f"Collection {name} does not exist.")

    monkeypatch.setattr(chroma_store, "client", lambda: FakeClient())
    assert chroma_store.delete(sid) is False


def test_chroma_delete_reraises_unrelated_value_error(monkeypatch):
    sid = "present-collection"

    class FakeClient:
        def delete_collection(self, name):
            raise ValueError("Collection chroma_some_other_session does not exist.")

    monkeypatch.setattr(chroma_store, "client", lambda: FakeClient())
    with pytest.raises(ValueError, match="chroma_some_other_session"):
        chroma_store.delete(sid)


def test_delete_endpoint_reports_unrelated_value_error_as_500(monkeypatch):
    doc_id = _setup_session_with_artifacts()

    def boom(document_id):
        raise ValueError("Collection chroma_some_other_session does not exist.")

    monkeypatch.setattr(session_store, "delete_collection", boom)
    resp = client.delete(f"/api/live/session/{doc_id}")
    assert resp.status_code == 500
    assert resp.json().get("deleted") is not True
    # The failure happens before the session JSON is removed, so retry is possible.
    assert session_store.load_session(doc_id) is not None


@pytest.mark.parametrize(
    "target",
    [
        "session_store._remove_audio",
        "observation_store.delete_observations",
        "consent_store.clear_consents",
        "session_store.delete_collection",
        "session_store._remove_session_record",
    ],
)
def test_failure_at_cleanup_stage_is_never_reported_as_success(monkeypatch, target):
    doc_id = _setup_session_with_artifacts()

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(f"app.services.{target}", boom)

    resp = client.delete(f"/api/live/session/{doc_id}")
    assert resp.status_code == 500
    assert resp.json().get("deleted") is not True
    # The session JSON is deleted last, so a mid-cleanup failure always leaves a
    # retryable session record behind.
    assert session_store.load_session(doc_id) is not None


def test_retry_after_failure_completes_cleanup(monkeypatch):
    doc_id = _setup_session_with_artifacts()
    original_clear = consent_store.clear_consents

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(consent_store, "clear_consents", boom)
    resp = client.delete(f"/api/live/session/{doc_id}")
    assert resp.status_code == 500
    assert session_store.load_session(doc_id) is not None

    # Remove only this injected failure (keep the conftest DATA_DIR isolation)
    # and retry: cleanup now completes.
    monkeypatch.setattr(consent_store, "clear_consents", original_clear)
    resp2 = client.delete(f"/api/live/session/{doc_id}")
    assert resp2.status_code == 200
    _assert_all_gone(doc_id)


def test_orphan_artifacts_cleaned_when_session_json_absent():
    doc_id = _setup_session_with_artifacts()

    # Simulate a prior partial deletion: only the session JSON is gone.
    (settings.DATA_DIR / "sessions" / f"{doc_id}.json").unlink()
    assert session_store.load_session(doc_id) is None
    assert (settings.DATA_DIR / "audio" / doc_id).exists()

    # A valid, safe id must still be cleaned up, not blocked by an early 404.
    resp = client.delete(f"/api/live/session/{doc_id}")
    assert resp.status_code == 200
    _assert_all_gone(doc_id)


def test_concurrent_consent_writes_are_not_lost():
    sid = "consent-race"
    per_thread = 40
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        for _ in range(per_thread):
            consent_store.record_consent(sid, "DE", ["X"], True)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(consent_store.get_consents(sid)) == 2 * per_thread


def test_concurrent_record_and_clear_do_not_lose_other_sessions():
    consent_store.record_consent("a", "DE", ["A"], True)
    consent_store.record_consent("b", "DE", ["B"], True)
    n = 40
    barrier = threading.Barrier(2)

    def recorder():
        barrier.wait()
        for _ in range(n):
            consent_store.record_consent("c", "DE", ["C"], True)

    def clearer():
        barrier.wait()
        for _ in range(n):
            consent_store.clear_consents("a")

    threads = [threading.Thread(target=recorder), threading.Thread(target=clearer)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert consent_store.get_consents("a") == []
    assert len(consent_store.get_consents("b")) == 1
    assert len(consent_store.get_consents("c")) == n


def test_clear_consents_preserves_malformed_and_other_lines():
    path = settings.DATA_DIR / consent_store.CONSENT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"timestamp":"t","session_id":"keep","country":"DE","participants":[],"consent_given":true,"notice_version":"1.0"}\n'
        "NOT JSON\n"
        '{"timestamp":"t","session_id":"drop","country":"DE","participants":[],"consent_given":true,"notice_version":"1.0"}\n',
        encoding="utf-8",
    )
    consent_store.clear_consents("drop")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # malformed line + keep line; the "drop" line is gone
    assert lines[0].startswith('{"timestamp"')
    assert lines[1] == "NOT JSON"
    # No temp file left behind after the atomic replacement.
    assert not path.with_name(path.name + ".tmp").exists()
