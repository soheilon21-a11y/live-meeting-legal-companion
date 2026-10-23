import logging
import threading
import time

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import live_worker, session_store, transcription
from main import app

client = TestClient(app)


def _make_session(session_id: str) -> None:
    session_store.create_session(session_id, "contract.txt")


def _fake_transcribe(file_bytes, **kwargs):
    return {"text": "hello world", "language": "en"}


def _record_consent(session_id: str) -> None:
    client.post(
        "/api/live/consent",
        json={
            "session_id": session_id,
            "country": "DE",
            "participants": ["A"],
            "consent_given": True,
        },
    )


def _upload_chunk(session_id: str, mode: str, chunk_index: int = 0):
    return client.post(
        f"/api/live/session/{session_id}/chunk",
        data={"chunk_index": chunk_index, "mode": mode},
        files={"file": (f"c{chunk_index}.webm", b"fake-audio", "audio/webm")},
    )


def _wait_for(fn, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return False


def test_chunk_full_without_consent_403():
    _make_session("c1")
    resp = _upload_chunk("c1", "full")
    assert resp.status_code == 403
    assert "refused" in resp.json()["detail"]


def test_chunk_full_with_consent_queued_and_saved(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("c2")
    _record_consent("c2")
    resp = _upload_chunk("c2", "full")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    audio = settings.DATA_DIR / "audio" / "c2" / "chunk_0.webm"
    assert audio.exists()
    assert audio.read_bytes() == b"fake-audio"


def test_chunk_dictation_no_consent(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("c3")
    resp = _upload_chunk("c3", "dictation")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_worker_processes_chunk_appends_transcript(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("c4")
    live_worker.enqueue_chunk("c4", 0, b"fake-audio")
    assert _wait_for(
        lambda: any(
            e.get("chunk_index") == 0 and e.get("text") == "hello world"
            for e in session_store.get_transcript("c4")
        )
    )


def test_status_reports_queue_depth(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_transcribe(b, **kwargs):
        started.set()
        release.wait(timeout=5)
        return {"text": "x", "language": "en"}

    monkeypatch.setattr(transcription, "transcribe_audio", slow_transcribe)
    _make_session("c5")
    live_worker.enqueue_chunk("c5", 0, b"a")
    live_worker.enqueue_chunk("c5", 1, b"b")
    assert started.wait(timeout=5)
    resp = client.get("/api/live/session/c5/status")
    assert resp.status_code == 200
    assert resp.json()["queue_depth"] >= 1
    release.set()


def test_stop_returns_final_counts(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("c6")
    live_worker.process_chunk("c6", 0, b"fake-audio")
    resp = client.post("/api/live/session/c6/stop")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recording"] is False
    assert body["processed"] >= 1


def test_live_transcript_since(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("c7")
    live_worker.process_chunk("c7", 0, b"a")
    live_worker.process_chunk("c7", 1, b"b")
    resp = client.get("/api/live/session/c7/transcript/live?since=0")
    assert resp.status_code == 200
    entries = resp.json()["transcript"]
    assert any(e["chunk_index"] == 1 for e in entries)
    assert all(e["chunk_index"] > 0 for e in entries)


def test_process_chunk_failure_logs_marker_no_leak(monkeypatch, caplog):
    def boom(b):
        raise RuntimeError("boom")

    monkeypatch.setattr(transcription, "transcribe_audio", boom)
    _make_session("fail1")
    with caplog.at_level(logging.ERROR, logger="app.services.live_worker"):
        live_worker.process_chunk("fail1", 7, b"\x00\x01\x02sensitive-audio")

    entry = next(
        e for e in session_store.get_transcript("fail1") if e.get("chunk_index") == 7
    )
    assert entry["text"] == "[transcription failed — audio preserved]"
    assert entry["language"] is None

    text = caplog.text
    assert "live transcription failed" in text
    assert "session=fail1" in text
    assert "chunk=7" in text
    assert "sensitive-audio" not in text
    assert "audio preserved" not in text


def test_flush_waits_for_inflight(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_transcribe(b, **kwargs):
        started.set()
        release.wait(timeout=5)
        return {"text": "x", "language": "en"}

    monkeypatch.setattr(transcription, "transcribe_audio", slow_transcribe)
    _make_session("inflight1")
    live_worker.enqueue_chunk("inflight1", 0, b"a")
    assert started.wait(timeout=5)

    result = {}

    def do_flush():
        result["n"] = live_worker.flush("inflight1")

    t = threading.Thread(target=do_flush)
    t.start()
    time.sleep(0.2)
    assert result == {}
    release.set()
    t.join(timeout=5)
    assert not t.is_alive()
    assert result["n"] == 0
