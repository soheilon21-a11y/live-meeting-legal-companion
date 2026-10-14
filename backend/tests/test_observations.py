from fastapi.testclient import TestClient

from app.services import observation_store, session_store
from main import app

client = TestClient(app)

FIXTURE = (
    "1. Term. The agreement shall commence on 1 January 2026 and continue for twelve months.\n"
    "2. Payment. The client shall pay the fee within thirty days of receipt of the invoice.\n"
    "3. Termination. Either party may terminate with ninety days written notice."
)


def _upload():
    return client.post(
        "/api/live/upload",
        files={"file": ("contract.txt", FIXTURE.encode("utf-8"), "text/plain")},
    )


def _append_live_chunk(session_id: str, chunk_index: int, text: str) -> None:
    session_store.append_transcript(
        session_id,
        {
            "timestamp": "2026-10-14T10:00:00+00:00",
            "mode": "live",
            "chunk_index": chunk_index,
            "text": text,
            "language": "en",
        },
    )


def test_observation_generated_when_relevant_passage():
    doc_id = _upload().json()["document_id"]
    _append_live_chunk(
        doc_id,
        1,
        "The agreement shall commence on 1 January 2026 and continue for twelve months.",
    )
    resp = client.get(
        f"/api/live/session/{doc_id}/observations?since=0&document_id={doc_id}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["last_index"] == 1
    assert len(body["observations"]) == 1
    obs = body["observations"][0]
    assert obs["evidence_status"] == "supported"
    assert obs["issue_question"].endswith("?")
    assert obs["transcript_excerpt"]
    assert obs["dismissed"] is False
    assert len(body["all"]) == 1


def test_no_observation_when_no_relevant_passage():
    session_id = "obs-irrelevant"
    session_store.create_session(session_id, "contract.txt")
    _append_live_chunk(
        session_id,
        1,
        "The weather forecast for tomorrow looks sunny and warm across the region.",
    )
    resp = client.get(f"/api/live/session/{session_id}/observations?since=0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["observations"] == []
    assert body["last_index"] == 1


def test_dismiss_marks_observation_for_audit():
    doc_id = _upload().json()["document_id"]
    _append_live_chunk(
        doc_id,
        1,
        "The agreement shall commence on 1 January 2026 and continue for twelve months.",
    )
    resp = client.get(
        f"/api/live/session/{doc_id}/observations?since=0&document_id={doc_id}"
    )
    obs_id = resp.json()["observations"][0]["obs_id"]

    dismiss_resp = client.post(
        f"/api/live/session/{doc_id}/observations/{obs_id}/dismiss"
    )
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["observations"] == []

    all_resp = client.get(f"/api/live/session/{doc_id}/observations/all")
    records = all_resp.json()["observations"]
    assert len(records) == 1
    assert records[0]["obs_id"] == obs_id
    assert records[0]["dismissed"] is True


def test_observation_store_round_trip():
    obs = observation_store.add_observation(
        "obs-store",
        {
            "issue_question": "Does this relate to the clause?",
            "evidence_status": "supported",
            "suggested_question": "Does the clause apply here?",
            "transcript_excerpt": "a transcript excerpt",
        },
    )
    assert obs["obs_id"]
    assert obs["dismissed"] is False

    records = observation_store.get_observations("obs-store")
    assert len(records) == 1
    assert records[0]["issue_question"] == "Does this relate to the clause?"

    assert observation_store.dismiss_observation("obs-store", obs["obs_id"]) is True
    records = observation_store.get_observations("obs-store")
    assert records[0]["dismissed"] is True
