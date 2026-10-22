from fastapi.testclient import TestClient

from app.services import analysis, ingest, session_store, transcription
from main import app

client = TestClient(app)

FIXTURE = (
    "1. Term. The agreement shall commence on 1 January 2026 and continue for twelve months.\n"
    "2. Payment. The client shall pay the fee within thirty days of receipt of the invoice.\n"
    "3. Termination. Either party may terminate with ninety days written notice."
)

PASSAGE = "The agreement shall commence on 1 January 2026 and continue for twelve months."


def _fake_transcribe(file_bytes):
    return {"text": "hello world", "language": "en"}


def _create_session() -> str:
    resp = client.post("/api/live/session")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert body["document_id"] == body["session_id"]
    return body["session_id"]


def test_create_session_without_document():
    sid = _create_session()
    session = session_store.load_session(sid)
    assert session is not None
    assert session["document_id"] == sid
    assert session["filename"] == ""
    assert session["findings"] == []
    assert session["transcript"] == []


def test_dictation_and_transcription_against_documentless_session(monkeypatch):
    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    sid = _create_session()

    resp = client.post(
        f"/api/live/session/{sid}/dictation",
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"

    client.post(
        "/api/live/consent",
        json={"session_id": sid, "country": "DE", "participants": ["A"], "consent_given": True},
    )
    resp = client.post(
        "/api/live/transcribe",
        data={"session_id": sid},
        files={"file": ("a.wav", b"fake", "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"


def test_analysis_insufficient_and_observations_empty():
    sid = _create_session()

    resp = client.post(
        "/api/live/analyze",
        json={"document_id": sid, "discussion_point": "When does the agreement commence?"},
    )
    assert resp.status_code == 200
    finding = resp.json()
    assert finding["evidence_status"] == "insufficient"
    assert finding["verbatim_passage"] == ""

    resp = client.get(f"/api/live/session/{sid}/observations?since=0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["observations"] == []
    assert body["all"] == []


def test_upload_document_to_same_session_afterwards_succeeds(monkeypatch):
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "passage_position": "passage 1 of 1",'
            ' "issue_question": "Does the agreement state a commencement date?",'
            ' "evidence_status": "supported",'
            ' "suggested_question": "Please confirm the commencement date."}'
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    sid = _create_session()
    ingest.ingest(sid, "contract.txt", FIXTURE.encode("utf-8"))

    resp = client.post(
        "/api/live/analyze",
        json={"document_id": sid, "discussion_point": "When does the agreement commence?"},
    )
    assert resp.status_code == 200
    finding = resp.json()
    assert finding["evidence_status"] == "supported"
    assert finding["verbatim_passage"] == PASSAGE
