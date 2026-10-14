import builtins

import numpy as np
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import diarization, session_store
from main import app

client = TestClient(app)


def _make_session(session_id: str) -> None:
    session_store.create_session(session_id, "contract.txt")


def _write_chunk(session_id: str, index: int) -> None:
    d = settings.DATA_DIR / "audio" / session_id
    d.mkdir(parents=True, exist_ok=True)
    (d / f"chunk_{index}.webm").write_bytes(b"fake-audio")


def _append_live(session_id: str, index: int, text: str) -> None:
    session_store.append_transcript(
        session_id,
        {
            "timestamp": "2026-10-14T10:00:00+00:00",
            "mode": "live",
            "chunk_index": index,
            "text": text,
            "language": "en",
        },
    )


def _fake_model():
    class Model:
        pass

    return Model()


def _fake_embedding(model, path):
    idx = diarization._chunk_index(path)
    return np.array([1.0, 0.0]) if idx % 2 == 0 else np.array([0.0, 1.0])


def test_diarize_assigns_speaker_labels(monkeypatch):
    monkeypatch.setattr(diarization, "_load_model", _fake_model)
    monkeypatch.setattr(diarization, "_extract_embedding", _fake_embedding)
    _make_session("d1")
    for i in (0, 1, 2):
        _write_chunk("d1", i)
    _append_live("d1", 0, "hello")
    _append_live("d1", 1, "world")
    _append_live("d1", 2, "again")

    resp = client.post("/api/live/session/d1/diarize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["speakers_detected"] == 2
    speakers = {e["chunk_index"]: e["speaker"] for e in body["transcript"]}
    assert speakers[0] == speakers[2]
    assert speakers[0] != speakers[1]

    get = client.get("/api/live/session/d1/transcript")
    assert get.status_code == 200
    entries = {e["chunk_index"]: e.get("speaker") for e in get.json()["transcript"]}
    assert entries[0] == entries[2]
    assert entries[1] != entries[0]


def test_diarize_not_enough_audio(monkeypatch):
    monkeypatch.setattr(diarization, "_load_model", _fake_model)
    _make_session("d2")
    _write_chunk("d2", 0)
    resp = client.post("/api/live/session/d2/diarize")
    assert resp.status_code == 503
    assert "Not enough audio" in resp.json()["detail"]


def test_correct_speaker(monkeypatch):
    monkeypatch.setattr(diarization, "_load_model", _fake_model)
    monkeypatch.setattr(diarization, "_extract_embedding", _fake_embedding)
    _make_session("d3")
    _write_chunk("d3", 0)
    _write_chunk("d3", 1)
    _append_live("d3", 0, "a")
    _append_live("d3", 1, "b")
    client.post("/api/live/session/d3/diarize")

    resp = client.post(
        "/api/live/session/d3/correct-speaker",
        json={"chunk_index": 0, "speaker": "Speaker 2"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is True
    speakers = {e["chunk_index"]: e["speaker"] for e in body["transcript"]}
    assert speakers[0] == "Speaker 2"


def test_cluster_and_label_speakers():
    embeddings = [
        np.array([1.0, 0.0]),
        np.array([0.0, 1.0]),
        np.array([1.0, 0.0]),
        np.array([0.0, 1.0]),
    ]
    labels = diarization._cluster(embeddings)
    names = diarization._label_speakers(labels)
    assert names[0] == "Speaker 1"
    assert names[1] == "Speaker 2"
    assert names[2] == names[0]
    assert names[3] == names[1]


def test_diarize_engine_unavailable(monkeypatch):
    diarization._model = None
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "speechbrain.inference.speaker":
            raise ImportError("No module named 'speechbrain'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    _make_session("d4")
    _write_chunk("d4", 0)
    _write_chunk("d4", 1)
    resp = client.post("/api/live/session/d4/diarize")
    assert resp.status_code == 503
    assert "install speechbrain and scikit-learn" in resp.json()["detail"]
