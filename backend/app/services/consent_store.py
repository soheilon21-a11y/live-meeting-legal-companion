import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

NOTICE_VERSION = "1.0"
CONSENT_FILENAME = "consent.jsonl"
FILE_MODE = 0o600


def _path() -> Path:
    return settings.DATA_DIR / CONSENT_FILENAME


def _ensure_file() -> Path:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    _chmod(path)
    return path


def _chmod(path: Path) -> None:
    try:
        os.chmod(path, FILE_MODE)
    except OSError:
        pass


def record_consent(
    session_id: str,
    country: str,
    participants: list[str],
    consent_given: bool,
    notice_version: str = NOTICE_VERSION,
) -> dict:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "country": country,
        "participants": participants,
        "consent_given": consent_given,
        "notice_version": notice_version,
    }
    path = _ensure_file()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    _chmod(path)
    return record


def get_consents(session_id: str) -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("session_id") == session_id:
                records.append(record)
    return records


def has_consent(session_id: str) -> bool:
    return any(record.get("consent_given") for record in get_consents(session_id))


def clear_consents(session_id: str) -> None:
    path = _path()
    if not path.exists():
        return
    kept = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                kept.append(raw)
                continue
            if record.get("session_id") != session_id:
                kept.append(raw)
    with path.open("w", encoding="utf-8") as f:
        f.writelines(kept)
    _chmod(path)
