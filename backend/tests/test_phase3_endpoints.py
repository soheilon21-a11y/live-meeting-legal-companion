from fastapi.testclient import TestClient

from app.services import live_worker, session_store, transcription
from main import app

client = TestClient(app)


def _make_session(session_id: str) -> None:
    session_store.create_session(session_id, "contract.txt")


def _fake_transcribe(file_bytes):
    return {"text": "hello world", "language": "en"}


def _fake_transcribe_assert_lock(file_bytes):
    assert live_worker.model_lock.locked()
    return {"text": "hello world", "language": "en"}


def test_country_endpoint():
    resp = client.get("/api/live/country/DE")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "§ 201 StGB (Germany)"
    assert "not legal advice" in body["disclaimer"]


def test_country_endpoint_unknown():
    resp = client.get("/api/live/country/ZZ")
    assert resp.status_code == 200
    assert resp.json()["source"] == "unverified"


def test_consent_endpoint_records():
    resp = client.post(
        "/api/live/consent",
        json={"session_id": "s1", "country": "DE", "participants": ["A"], "consent_given": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s1"
    assert len(body["consents"]) == 1
    assert body["consents"][0]["consent_given"] is True


def test_transcribe_refused_without_consent():
    _make_session("s2")
    resp = client.post(
        "/api/live/transcribe",
        data={"session_id": "s2"},
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 403
    assert "refused" in resp.json()["detail"]


def test_transcribe_allowed_with_consent(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("s3")
    client.post(
        "/api/live/consent",
        json={"session_id": "s3", "country": "DE", "participants": ["A"], "consent_given": True},
    )
    resp = client.post(
        "/api/live/transcribe",
        data={"session_id": "s3"},
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"


def test_dictation_works_without_consent(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("s4")
    resp = client.post(
        "/api/live/session/s4/dictation",
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"


def test_transcript_endpoint(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    _make_session("s5")
    client.post(
        "/api/live/session/s5/dictation",
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    resp = client.get("/api/live/session/s5/transcript")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s5"
    assert len(body["transcript"]) == 1
    assert body["transcript"][0]["text"] == "hello world"
    assert body["transcript"][0]["mode"] == "dictation"


def test_transcribe_holds_model_lock(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe_assert_lock)
    _make_session("lock1")
    client.post(
        "/api/live/consent",
        json={"session_id": "lock1", "country": "DE", "participants": ["A"], "consent_given": True},
    )
    resp = client.post(
        "/api/live/transcribe",
        data={"session_id": "lock1"},
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200


def test_dictation_holds_model_lock(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe_assert_lock)
    _make_session("lock2")
    resp = client.post(
        "/api/live/session/lock2/dictation",
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200


def test_transcribe_engine_unavailable(monkeypatch):
    def boom(file_bytes):
        raise RuntimeError("Transcription engine not available — install faster-whisper")

    monkeypatch.setattr(transcription, "transcribe_audio", boom)
    _make_session("s6")
    client.post(
        "/api/live/consent",
        json={"session_id": "s6", "country": "DE", "participants": ["A"], "consent_given": True},
    )
    resp = client.post(
        "/api/live/transcribe",
        data={"session_id": "s6"},
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 503
