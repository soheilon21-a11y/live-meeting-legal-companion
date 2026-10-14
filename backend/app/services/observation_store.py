import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


def _observations_dir() -> Path:
    d = settings.DATA_DIR / "observations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(session_id: str) -> Path:
    return _observations_dir() / f"{session_id}.json"


def _load(session_id: str) -> list[dict]:
    p = _path(session_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save(session_id: str, observations: list[dict]) -> None:
    _path(session_id).write_text(json.dumps(observations), encoding="utf-8")


def add_observation(session_id: str, observation: dict) -> dict:
    record = {
        "obs_id": uuid.uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issue_question": observation.get("issue_question", ""),
        "evidence_status": observation.get("evidence_status", "insufficient"),
        "suggested_question": observation.get("suggested_question"),
        "transcript_excerpt": observation.get("transcript_excerpt", ""),
        "dismissed": False,
    }
    observations = _load(session_id)
    observations.append(record)
    _save(session_id, observations)
    return record


def get_observations(session_id: str) -> list[dict]:
    return _load(session_id)


def dismiss_observation(session_id: str, obs_id: str) -> bool:
    observations = _load(session_id)
    for obs in observations:
        if obs.get("obs_id") == obs_id:
            obs["dismissed"] = True
            _save(session_id, observations)
            return True
    return False
