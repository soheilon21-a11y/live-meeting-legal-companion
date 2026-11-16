import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.services import consent_store, observation_store
from app.services.chroma_store import delete as delete_collection

# Serializes the session JSON read-modify-write cycles performed across the
# live-worker daemon and the uvicorn threadpool. A data-layer mutex only: it
# does NOT enable concurrent model execution (models remain serialized by
# live_worker.model_lock).
_lock = threading.RLock()

# Session IDs are server-generated uuid4().hex (32 lowercase hex). We also
# accept simple alphanumeric test identifiers, but reject anything that could
# traverse outside DATA_DIR (path separators, dot segments, drive prefixes).
_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def valid_session_id(session_id: str) -> bool:
    """Return True when ``session_id`` is safe to use as a path component."""
    return isinstance(session_id, str) and bool(_SAFE_SESSION_ID.match(session_id))


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


def _remove_audio(session_id: str) -> bool:
    """Remove the session's audio-chunk directory (idempotent)."""
    audio_dir = settings.DATA_DIR / "audio" / session_id
    if audio_dir.exists():
        shutil.rmtree(audio_dir)
        return True
    return False


def _remove_session_record(session_id: str) -> bool:
    """Remove the session JSON record (idempotent)."""
    p = _path(session_id)
    if p.exists():
        p.unlink()
        return True
    return False


def delete_session(session_id: str) -> bool:
    """Delete a session and every associated artifact.

    Removes, in order: audio chunks, observations, session-specific consent
    records, the Chroma vector collection, and finally the session JSON. The
    session JSON is deleted **last** so an intermediate failure leaves a
    retryable session record rather than stranding orphan artifacts.

    Every step is idempotent, so a second request finishes a partially
    completed deletion, and orphan cleanup still runs when the session JSON is
    already absent. Returns True when any artifact was removed; raises
    ``ValueError`` for an unsafe ``session_id`` and propagates storage/database
    errors so callers never report success on incomplete cleanup.
    """
    if not valid_session_id(session_id):
        raise ValueError(f"invalid session id: {session_id!r}")

    removed = False

    # Audio chunks (recursive directory removal).
    if _remove_audio(session_id):
        removed = True

    # Observations.
    if observation_store.delete_observations(session_id):
        removed = True

    # Session-specific consent records (preserves other sessions' records).
    if consent_store.clear_consents(session_id):
        removed = True

    # Vector collection (missing collection == already deleted).
    if delete_collection(session_id):
        removed = True

    # Session JSON last: keep the retryable marker until everything else is gone.
    if _remove_session_record(session_id):
        removed = True

    return removed
