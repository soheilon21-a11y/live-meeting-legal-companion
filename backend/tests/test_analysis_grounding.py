import threading

from fastapi.testclient import TestClient

from app.services import analysis, retrieval, session_store
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


def _analyze(doc_id, point):
    return client.post(
        "/api/live/analyze",
        json={"document_id": doc_id, "discussion_point": point},
    )


def _grounded(verbatim=PASSAGE, position="passage 1 of 1", issue="Does the agreement state a commencement date?",
              status="supported", suggested=""):
    return (
        '{"verbatim_passage": "' + verbatim + '",'
        ' "passage_position": "' + position + '",'
        ' "issue_question": "' + issue + '",'
        ' "evidence_status": "' + status + '",'
        ' "suggested_question": "' + suggested + '"}'
    )


def test_invented_quotation_is_rejected(monkeypatch):
    # The model returns a passage that is NOT verbatim in the document.
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "The agreement shall pay one million dollars.",'
            ' "issue_question": "Does the agreement require a million dollar payment?",'
            ' "evidence_status": "supported",'
            ' "suggested_question": "Confirm the payment amount."}',
            None,
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "How much must be paid?").json()
    assert finding["mode"] == "retrieval_only"
    # The fallback returns a real, verbatim passage (never the invented one).
    assert finding["verbatim_passage"] in FIXTURE
    assert "million dollars" not in finding["verbatim_passage"]


def test_verbatim_quotation_is_accepted(monkeypatch):
    def fake_llm(prompt):
        return (_grounded(), None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "llm_grounded"
    assert finding["verbatim_passage"] == PASSAGE


def test_wrong_model_position_is_ignored_and_backend_position_used(monkeypatch):
    # Valid verbatim quote, but the model reports a position that does not
    # exist. Grounding is based on the backend passage, and the returned
    # position is derived from that passage's backend metadata.
    def fake_llm(prompt):
        return (_grounded(position="passage 99 of 1"), None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "llm_grounded"
    assert finding["verbatim_passage"] == PASSAGE
    assert finding["passage_position"] == "passage 1 of 1"


def test_missing_model_position_does_not_prevent_grounded_finding(monkeypatch):
    # The reduced response schema no longer asks for passage_position; an
    # otherwise valid grounded finding must still be accepted.
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "issue_question": "Does the agreement state a commencement date?",'
            ' "evidence_status": "supported"}',
            None,
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "llm_grounded"
    assert finding["verbatim_passage"] == PASSAGE
    assert finding["passage_position"] == "passage 1 of 1"


def test_prompt_no_longer_asks_for_passage_position(monkeypatch):
    prompts = []

    def fake_llm(prompt):
        prompts.append(prompt)
        return (_grounded(), None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    _analyze(doc_id, "When does the agreement commence?")
    assert "passage_position" not in prompts[0]


def test_first_matching_passage_wins_in_retrieval_order():
    # The same quotation may appear in overlapping chunks; selection is
    # deterministic and follows retrieval order.
    passages = [
        {"text": "filler before " + PASSAGE, "position": "passage 1 of 3"},
        {"text": PASSAGE + " filler after", "position": "passage 2 of 3"},
    ]
    matched = analysis._match_passage(PASSAGE, passages)
    assert matched is passages[0]
    assert matched["position"] == "passage 1 of 3"


def test_invalid_evidence_status_is_rejected(monkeypatch):
    def fake_llm(prompt):
        return (_grounded(status="banana"), None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"


def test_wrong_field_type_is_rejected(monkeypatch):
    # issue_question must be a string; an object is rejected.
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "issue_question": {"nested": true},'
            ' "evidence_status": "supported"}',
            None,
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"


def test_unsupported_suggested_question_structure_is_rejected(monkeypatch):
    # suggested_question must be a string (or omitted); a list is rejected.
    def fake_llm(prompt):
        return (
            '{"verbatim_passage": "' + PASSAGE + '",'
            ' "issue_question": "Does the agreement state a commencement date?",'
            ' "evidence_status": "supported",'
            ' "suggested_question": ["a", "b"]}',
            None,
        )

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"


def test_malformed_json_is_rejected(monkeypatch):
    def fake_llm(prompt):
        return ("not json at all {", None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"


def test_empty_retrieval_is_honest(monkeypatch):
    # No retrieved passages -> explicit insufficient result, no LLM call.
    monkeypatch.setattr(retrieval, "retrieve", lambda document_id, query: [])
    calls = {"n": 0}

    def fake_llm(prompt):
        calls["n"] += 1
        return (_grounded(), None)

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"
    assert finding["evidence_status"] == "insufficient"
    assert finding["verbatim_passage"] == ""
    assert calls["n"] == 0  # the model was never called


def test_retry_then_success(monkeypatch):
    calls = {"n": 0}

    def flaky_llm(prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient failure")
        return (_grounded(), None)

    monkeypatch.setattr(analysis, "_call_llm", flaky_llm)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "llm_grounded"
    assert calls["n"] == 2


def test_exhausted_retries_fall_back(monkeypatch):
    # LLM_MAX_RETRIES=2 means 1 initial attempt + 2 retries = 3 total attempts.
    calls = {"n": 0}

    def always_boom(prompt):
        calls["n"] += 1
        raise RuntimeError("down")

    monkeypatch.setattr(analysis, "_call_llm", always_boom)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"
    assert calls["n"] == 3


def test_zero_retries_still_makes_one_call(monkeypatch):
    calls = {"n": 0}

    def boom(prompt):
        calls["n"] += 1
        raise RuntimeError("down")

    monkeypatch.setattr(analysis, "_call_llm", boom)
    monkeypatch.setattr(analysis.settings, "LLM_MAX_RETRIES", 0)
    doc_id = _upload().json()["document_id"]
    finding = _analyze(doc_id, "When does the agreement commence?").json()
    assert finding["mode"] == "retrieval_only"
    assert calls["n"] == 1


def test_finding_stores_traceability_metadata(monkeypatch):
    usage = {"model": "llama3:latest", "prompt_tokens": 100, "completion_tokens": 50}

    def fake_llm(prompt):
        return (_grounded(), dict(usage))

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_id = _upload().json()["document_id"]
    _analyze(doc_id, "When does the agreement commence?")
    stored = session_store.load_session(doc_id)["findings"][0]
    assert stored["source"] == "llm_grounded"
    assert stored["model"] == "llama3:latest"
    assert stored["usage"] == usage


def test_concurrent_analyses_store_their_own_usage(monkeypatch):
    # Two concurrent analyses with distinct token counts must each attach their
    # own usage to their own finding (no request-scoped cross-contamination).
    def fake_llm(prompt):
        if "point-a" in prompt:
            return (_grounded(), {"model": "model-A", "prompt_tokens": 11, "completion_tokens": 22})
        return (_grounded(), {"model": "model-B", "prompt_tokens": 33, "completion_tokens": 44})

    monkeypatch.setattr(analysis, "_call_llm", fake_llm)
    doc_a = _upload().json()["document_id"]
    doc_b = _upload().json()["document_id"]

    barrier = threading.Barrier(2)
    results = {}

    def run(key, doc_id, point):
        barrier.wait()
        results[key] = _analyze(doc_id, point).json()

    threads = [
        threading.Thread(target=run, args=("a", doc_a, "point-a: When does the agreement commence?")),
        threading.Thread(target=run, args=("b", doc_b, "point-b: When does the agreement commence?")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results["a"]["mode"] == "llm_grounded"
    assert results["b"]["mode"] == "llm_grounded"

    stored_a = session_store.load_session(doc_a)["findings"][0]
    stored_b = session_store.load_session(doc_b)["findings"][0]
    assert stored_a["model"] == "model-A"
    assert stored_a["usage"] == {"model": "model-A", "prompt_tokens": 11, "completion_tokens": 22}
    assert stored_b["model"] == "model-B"
    assert stored_b["usage"] == {"model": "model-B", "prompt_tokens": 33, "completion_tokens": 44}
