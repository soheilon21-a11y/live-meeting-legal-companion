import builtins

import pytest
from fastapi.testclient import TestClient

from app.services import session_store, tts
from main import app

client = TestClient(app)


class FakeVoice:
    def synthesize_wav(self, text, wav_file):
        wav_file.setframerate(22050)
        wav_file.setsampwidth(2)
        wav_file.setnchannels(1)
        wav_file.writeframes(b"\x00\x00\x00\x00")


def _make_session(session_id: str) -> None:
    session_store.create_session(session_id, "contract.txt")


def test_speak_valid_text_returns_wav_bytes(monkeypatch):
    monkeypatch.setattr(tts, "_load_voice", lambda lang: FakeVoice())
    audio = tts.speak("The agreement shall commence on 1 January 2026.")
    assert isinstance(audio, bytes)
    assert audio.startswith(b"RIFF")


def test_speak_empty_text_raises(monkeypatch):
    monkeypatch.setattr(tts, "_load_voice", lambda lang: FakeVoice())
    with pytest.raises(ValueError, match="empty"):
        tts.speak("   ")


def test_unsupported_language_falls_back_to_en():
    assert tts._voice_name("de") == tts.DE_VOICE
    assert tts._voice_name("en") == tts.EN_VOICE
    assert tts._voice_name("fr") == tts.EN_VOICE
    assert tts._voice_name("") == tts.EN_VOICE
    assert tts._voice_name(None) == tts.EN_VOICE


def test_speak_unsupported_language_no_error(monkeypatch):
    monkeypatch.setattr(tts, "_load_voice", lambda lang: FakeVoice())
    audio = tts.speak("hello", "xx")
    assert audio.startswith(b"RIFF")


def test_speak_long_text_truncates(monkeypatch):
    seen = {}

    class RecVoice:
        def synthesize_wav(self, text, wav_file):
            seen["text"] = text
            wav_file.setframerate(22050)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(b"\x00\x00")

    monkeypatch.setattr(tts, "_load_voice", lambda lang: RecVoice())
    tts.speak("x" * (tts.MAX_CHARS + 50))
    assert len(seen["text"]) <= tts.MAX_CHARS + 1


def test_speak_engine_not_installed(monkeypatch):
    tts._voices.clear()
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "piper":
            raise ImportError("No module named 'piper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="install piper-tts"):
        tts.speak("hello")


def test_speak_endpoint_returns_wav(monkeypatch):
    monkeypatch.setattr(tts, "speak", lambda text, lang="en": b"RIFF" + b"\x00" * 16)
    _make_session("t1")
    resp = client.post(
        "/api/live/session/t1/speak",
        json={"text": "hello", "lang": "en"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content.startswith(b"RIFF")


def test_speak_endpoint_empty_text(monkeypatch):
    monkeypatch.setattr(tts, "speak", lambda text, lang="en": b"RIFF")
    _make_session("t2")
    resp = client.post("/api/live/session/t2/speak", json={"text": "  "})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_speak_endpoint_engine_unavailable(monkeypatch):
    def boom(text, lang="en"):
        raise RuntimeError("TTS engine not available — install piper-tts")

    monkeypatch.setattr(tts, "speak", boom)
    _make_session("t3")
    resp = client.post(
        "/api/live/session/t3/speak",
        json={"text": "hello", "lang": "en"},
    )
    assert resp.status_code == 503
    assert "install piper-tts" in resp.json()["detail"]


def test_speak_endpoint_unknown_session():
    resp = client.post(
        "/api/live/session/missing/speak",
        json={"text": "hello", "lang": "en"},
    )
    assert resp.status_code == 404


def test_speak_endpoint_truncation_header(monkeypatch):
    monkeypatch.setattr(tts, "speak", lambda text, lang="en": b"RIFF")
    _make_session("t4")
    resp = client.post(
        "/api/live/session/t4/speak",
        json={"text": "x" * (tts.MAX_CHARS + 10), "lang": "en"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Audio-Truncated") == "true"
