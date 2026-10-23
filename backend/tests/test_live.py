import logging

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import analysis
from main import app

client = TestClient(app)

FIXTURE = (
    "1. Term. The agreement shall commence on 1 January 2026 and continue for twelve months.\n"
    "2. Payment. The client shall pay the fee within thirty days of receipt of the invoice.\n"
    "3. Termination. Either party may terminate with ninety days written notice."
)

PASSAGE = "The agreement shall commence on 1 January 2026 and continue for twelve months."


def _upload():
    return client.post(
        "/api/live/upload",
        files={"file": ("contract.txt", FIXTURE.encode("utf-8"), "text/plain")},
    )


def test_upload_and_analyze_returns_verbatim_passage(monkeypatch):
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "passage_position": "passage 1 of 1",'
            ' "issue_question": "Does the agreement state a commencement date?",'
            ' "evidence_status": "supported",'
            ' "suggested_question": "Please confirm the commencement date."}'
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    up = _upload()
    assert up.status_code == 200
    doc_id = up.json()["document_id"]

    resp = client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "When does the agreement commence?"},
    )
    assert resp.status_code == 200
    finding = resp.json()
    assert finding["mode"] == "llm_grounded"
    assert finding["evidence_status"] == "supported"
    assert finding["verbatim_passage"] == PASSAGE
    assert finding["verbatim_passage"] in FIXTURE
    assert finding["draft_label"] == "draft — review required"


def test_insufficient_irrelevant_point(monkeypatch):
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "",'
            ' "passage_position": "",'
            ' "issue_question": "No relevant passage found for this discussion point.",'
            ' "evidence_status": "insufficient",'
            ' "suggested_question": ""}'
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    doc_id = _upload().json()["document_id"]
    resp = client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "What is the weather forecast for tomorrow?"},
    )
    finding = resp.json()
    assert finding["evidence_status"] == "insufficient"
    assert finding["verbatim_passage"] == ""


def test_retrieval_only_fallback(monkeypatch):
    def boom(prompt):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(analysis, "_call_llm", boom)

    doc_id = _upload().json()["document_id"]
    resp = client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "When does the agreement commence?"},
    )
    finding = resp.json()
    assert finding["mode"] == "retrieval_only"
    assert finding["evidence_status"] == "insufficient"
    assert finding["verbatim_passage"]
    assert finding["verbatim_passage"] in FIXTURE


def test_empty_parse_falls_back_to_retrieval(monkeypatch):
    def fake_llm(prompt):
        return '{"verbatim_passage": "", "issue_question": "", "evidence_status": "insufficient"}'

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    doc_id = _upload().json()["document_id"]
    resp = client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "When does the agreement commence?"},
    )
    finding = resp.json()
    assert finding["mode"] == "retrieval_only"
    assert finding["evidence_status"] == "insufficient"
    assert finding["verbatim_passage"]
    assert finding["verbatim_passage"] in FIXTURE


def test_degenerate_output_does_not_log_content(monkeypatch, caplog):
    def fake_llm(prompt):
        return "unparsable: The agreement shall commence on 1 January 2026"

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    doc_id = _upload().json()["document_id"]
    with caplog.at_level(logging.WARNING, logger="app.services.analysis"):
        client.post(
            "/api/live/analyze",
            json={"document_id": doc_id, "discussion_point": "When does the agreement commence?"},
        )

    assert "degenerate" in caplog.text
    assert "commence on 1 January 2026" not in caplog.text


def test_short_valid_finding_not_downgraded(monkeypatch):
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "",'
            ' "passage_position": "",'
            ' "issue_question": "Does the contract address termination?",'
            ' "evidence_status": "insufficient",'
            ' "suggested_question": ""}'
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    doc_id = _upload().json()["document_id"]
    resp = client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "How is the agreement terminated?"},
    )
    finding = resp.json()
    assert finding["mode"] == "llm_grounded"
    assert finding["issue_question"] == "Does the contract address termination?"
    assert finding["verbatim_passage"] == ""


def test_export_returns_pdf(monkeypatch):
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "passage_position": "passage 1 of 1",'
            ' "issue_question": "Does the agreement state a commencement date?",'
            ' "evidence_status": "supported",'
            ' "suggested_question": "Please confirm the commencement date."}'
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)

    doc_id = _upload().json()["document_id"]
    client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": "When does the agreement commence?"},
    )
    resp = client.get(f"/api/live/session/{doc_id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["cache-control"] == "no-store"
    assert resp.content.startswith(b"%PDF")


def test_delete_removes_collection_and_session_files():
    session_id = _upload().json()["session_id"]
    session_file = settings.DATA_DIR / "sessions" / f"{session_id}.json"
    assert session_file.exists()
    assert client.get(f"/api/live/session/{session_id}/findings").status_code == 200

    resp = client.delete(f"/api/live/session/{session_id}")
    assert resp.status_code == 200

    assert not session_file.exists()
    assert client.get(f"/api/live/session/{session_id}/findings").status_code == 404

    from app.services.chroma_store import client as chroma_client

    names = [c.name for c in chroma_client().list_collections()]
    assert f"chroma_{session_id}" not in names
