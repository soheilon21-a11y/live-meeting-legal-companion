import json
import os
import stat

import pytest

from app.core.config import settings
from app.services import consent_store


def test_record_and_get_consents():
    consent_store.record_consent("s1", "DE", ["A", "B"], True)
    consent_store.record_consent("s1", "DE", ["A", "B"], False)
    records = consent_store.get_consents("s1")
    assert len(records) == 2
    assert records[0]["consent_given"] is True
    assert records[1]["consent_given"] is False
    assert records[0]["session_id"] == "s1"
    assert records[0]["country"] == "DE"
    assert records[0]["participants"] == ["A", "B"]
    assert records[0]["notice_version"] == consent_store.NOTICE_VERSION
    assert "timestamp" in records[0]


def test_jsonl_format_is_valid_lines():
    consent_store.record_consent("s2", "US", ["X"], True)
    path = settings.DATA_DIR / consent_store.CONSENT_FILENAME
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["session_id"] == "s2"


def test_has_consent_requires_true():
    assert consent_store.has_consent("s3") is False
    consent_store.record_consent("s3", "DE", ["A"], False)
    assert consent_store.has_consent("s3") is False
    consent_store.record_consent("s3", "DE", ["A"], True)
    assert consent_store.has_consent("s3") is True


def test_clear_consents_removes_only_that_session():
    consent_store.record_consent("s4", "DE", ["A"], True)
    consent_store.record_consent("s5", "DE", ["B"], True)
    consent_store.clear_consents("s4")
    assert consent_store.get_consents("s4") == []
    assert len(consent_store.get_consents("s5")) == 1


def test_consent_file_is_append_only():
    consent_store.record_consent("s6", "DE", ["A"], True)
    first = consent_store.get_consents("s6")
    consent_store.record_consent("s6", "DE", ["A"], False)
    second = consent_store.get_consents("s6")
    assert len(first) == 1
    assert len(second) == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only file permission bits")
def test_consent_file_permissions():
    consent_store.record_consent("s7", "DE", ["A"], True)
    path = settings.DATA_DIR / consent_store.CONSENT_FILENAME
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
