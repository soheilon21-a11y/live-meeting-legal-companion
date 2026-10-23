from fastapi.testclient import TestClient

from app.services import session_store
from main import app

client = TestClient(app)


def _make_session(session_id):
    session_store.create_session(session_id, "")


def _record_consent(session_id):
    client.post(
        "/api/live/consent",
        json={
            "session_id": session_id,
            "country": "DE",
            "participants": ["A"],
            "consent_given": True,
        },
    )


def _chunk(session_id, mode, chunk_index=0):
    return client.post(
        f"/api/live/session/{session_id}/chunk",
        data={"chunk_index": chunk_index, "mode": mode},
        files={"file": (f"c{chunk_index}.webm", b"fake-audio", "audio/webm")},
    )


def _transcribe(session_id):
    return client.post(
        "/api/live/transcribe",
        data={"session_id": session_id},
        files={"file": ("a.wav", b"fake-audio", "audio/wav")},
    )


def _dictation(session_id):
    return client.post(
        f"/api/live/session/{session_id}/dictation",
        files={"file": ("a.wav", b"fake-audio", "audio/wav")},
    )


def _disable(session_id):
    return client.post(
        f"/api/live/session/{session_id}/capture",
        json={"capture_disabled": True},
    )


def test_unknown_session_capture_404():
    resp = client.post(
        "/api/live/session/does-not-exist/capture",
        json={"capture_disabled": True},
    )
    assert resp.status_code == 404


def test_disabled_rejects_all_endpoints():
    _make_session("a1")
    _record_consent("a1")
    assert _disable("a1").status_code == 200

    assert _chunk("a1", "full", 0).status_code == 409
    assert _chunk("a1", "dictation", 1).status_code == 409
    assert _transcribe("a1").status_code == 409
    assert _dictation("a1").status_code == 409


def test_legacy_without_flag_allowed(monkeypatch):
    monkeypatch.setattr(
        "app.services.transcription.transcribe_audio",
        lambda b: {"text": "ok", "language": "en"},
    )
    _make_session("b1")
    resp = _dictation("b1")
    assert resp.status_code == 200
    assert resp.json()["text"] == "ok"


def test_toggle_first_200_then_409(monkeypatch):
    monkeypatch.setattr(
        "app.services.transcription.transcribe_audio",
        lambda b: {"text": "ok", "language": "en"},
    )
    _make_session("c1")
    assert _chunk("c1", "dictation", 0).status_code == 200
    assert _disable("c1").status_code == 200
    assert _chunk("c1", "dictation", 1).status_code == 409


def test_full_without_consent_403_even_when_disabled():
    _make_session("d1")
    assert _disable("d1").status_code == 200
    assert _chunk("d1", "full", 0).status_code == 403


def test_disabled_with_consent_still_409():
    _make_session("d2")
    _record_consent("d2")
    assert _disable("d2").status_code == 200
    assert _chunk("d2", "full", 0).status_code == 409


def test_control_events_carry_ts_and_boolean_only():
    _make_session("e1")
    session_store.set_capture_disabled("e1", True)
    session_store.set_capture_disabled("e1", False)
    events = session_store.load_session("e1")["control_events"]
    assert len(events) == 2
    for ev in events:
        assert set(ev.keys()) == {"ts", "capture_disabled"}
        assert isinstance(ev["capture_disabled"], bool)
        assert isinstance(ev["ts"], str)
        assert "T" in ev["ts"]


def test_status_exposes_flag():
    _make_session("f1")
    assert client.get("/api/live/session/f1/status").json()["capture_disabled"] is False
    assert _disable("f1").status_code == 200
    assert client.get("/api/live/session/f1/status").json()["capture_disabled"] is True
