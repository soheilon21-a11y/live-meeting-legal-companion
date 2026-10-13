import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.services.chroma_store import delete as delete_collection


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
    }
    _path(session_id).write_text(json.dumps(data), encoding="utf-8")
    return data


def load_session(session_id: str) -> dict | None:
    p = _path(session_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def add_finding(session_id: str, finding: dict) -> None:
    data = load_session(session_id)
    data["findings"].append(finding)
    _path(session_id).write_text(json.dumps(data), encoding="utf-8")


def delete_session(session_id: str) -> None:
    p = _path(session_id)
    if p.exists():
        p.unlink()
    try:
        delete_collection(session_id)
    except Exception:
        pass
