import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

NOTICE_VERSION = "1.0"
CONSENT_FILENAME = "consent.jsonl"
FILE_MODE = 0o600

# Serializes the consent.jsonl read-modify-write cycles so concurrent record
# and clear operations cannot lose other sessions' records.
_lock = threading.Lock()


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


def _atomic_replace(path: Path, lines: list[str]) -> None:
    """Write ``lines`` to a sibling temp file and atomically replace ``path``.

    The live file is never truncated before the replacement is complete, so a
    crash mid-write cannot leave a partially-written consent file. The temp file
    is cleaned up on success and on failure.
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    _chmod(path)


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
    with _lock:
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


def clear_consents(session_id: str) -> bool:
    """Remove only ``session_id``'s records, preserving all unrelated lines.

    Uses a read-modify-write cycle under the process lock, then atomically
    replaces the file so a crash cannot strand a partially-written consent file.
    Malformed/unrecognized lines are preserved verbatim. Returns True when at
    least one record was removed.
    """
    path = _path()
    if not path.exists():
        return False
    with _lock:
        kept = []
        removed = False
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
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
                else:
                    removed = True
        _atomic_replace(path, kept)
    return removed
