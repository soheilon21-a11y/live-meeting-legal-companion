import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.services.chroma_store import delete as delete_collection

# Serializes the session JSON read-modify-write cycles performed across the
# live-worker daemon and the uvicorn threadpool. A data-layer mutex only: it
# does NOT enable concurrent model execution (models remain serialized by
# live_worker.model_lock).
_lock = threading.RLock()


def _sessions_dir() -> Path:
    d = settings.DATA_DIR / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(session_id: str) -> Path:
    return _sessions_dir() / f"{session_id}.json"


def create_session(session_id: str, filename: str) -> dict:
    data = {
        "session_id": session_id,
        "document_id": session_id,
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "findings": [],
        "transcript": [],
    }
    _path(session_id).write_text(json.dumps(data), encoding="utf-8")
    return data


def load_session(session_id: str) -> dict | None:
    p = _path(session_id)
    with _lock:
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))


def add_finding(session_id: str, finding: dict) -> None:
    with _lock:
        data = load_session(session_id)
        data["findings"].append(finding)
        _path(session_id).write_text(json.dumps(data), encoding="utf-8")


def append_transcript(session_id: str, entry: dict) -> None:
    with _lock:
        data = load_session(session_id)
        data.setdefault("transcript", [])
        data["transcript"].append(entry)
        _path(session_id).write_text(json.dumps(data), encoding="utf-8")


def get_transcript(session_id: str) -> list[dict]:
    with _lock:
        data = load_session(session_id)
        if data is None:
            return []
        return data.get("transcript", [])


def apply_speakers(session_id: str, chunk_speakers: dict[int, str]) -> None:
    with _lock:
        data = load_session(session_id)
        for entry in data.get("transcript", []):
            idx = entry.get("chunk_index")
            if idx in chunk_speakers:
                entry["speaker"] = chunk_speakers[idx]
        _path(session_id).write_text(json.dumps(data), encoding="utf-8")


def set_speaker(session_id: str, chunk_index: int, speaker: str) -> bool:
    with _lock:
        data = load_session(session_id)
        updated = False
        for entry in data.get("transcript", []):
            if entry.get("chunk_index") == chunk_index:
                entry["speaker"] = speaker
                updated = True
        _path(session_id).write_text(json.dumps(data), encoding="utf-8")
        return updated


def set_capture_disabled(session_id: str, disabled: bool) -> None:
    with _lock:
        data = load_session(session_id)
        data["capture_disabled"] = disabled
        data.setdefault("control_events", []).append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "capture_disabled": disabled,
            }
        )
        _path(session_id).write_text(json.dumps(data), encoding="utf-8")


def delete_session(session_id: str) -> None:
    p = _path(session_id)
    if p.exists():
        p.unlink()
    try:
        delete_collection(session_id)
    except Exception:
        pass
