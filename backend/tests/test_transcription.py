import builtins

import pytest

from app.services import transcription


def test_transcribe_mocked_model(monkeypatch):
    class FakeInfo:
        language = "en"

    class FakeSegment:
        text = " hello "

    class FakeModel:
        def transcribe(self, audio, beam_size=5):
            return [FakeSegment()], FakeInfo()

    monkeypatch.setattr(transcription, "_load_model", lambda: FakeModel())
    result = transcription.transcribe_audio(b"fake audio")
    assert result == {"text": "hello", "language": "en"}


def test_transcribe_raises_if_engine_not_installed(monkeypatch):
    transcription._model = None
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("No module named 'faster_whisper'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="install faster-whisper"):
        transcription.transcribe_audio(b"fake audio")
