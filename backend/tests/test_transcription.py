import builtins

import pytest

from app.core.config import settings
from app.services import live_worker, session_store, transcription


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


def test_transcribe_audio_without_kwargs_forwards_nothing(monkeypatch):
    class FakeInfo:
        language = "en"

    class FakeSegment:
        text = "hi"

    class FakeModel:
        def __init__(self):
            self.kwargs = None

        def transcribe(self, audio, beam_size=5, **kwargs):
            self.kwargs = kwargs
            return [FakeSegment()], FakeInfo()

    model = FakeModel()
    monkeypatch.setattr(transcription, "_load_model", lambda: model)
    result = transcription.transcribe_audio(b"fake audio")
    assert result == {"text": "hi", "language": "en"}
    assert model.kwargs == {}


def test_transcribe_audio_with_kwargs_keeps_response_shape(monkeypatch):
    class FakeInfo:
        language = "en"

    class FakeSegment:
        text = "contract clause"

    class FakeModel:
        def transcribe(self, audio, beam_size=5, **kwargs):
            assert kwargs["language"] == "de"
            assert kwargs["initial_prompt"] == "contract"
            assert kwargs["condition_on_previous_text"] is False
            assert kwargs["no_speech_threshold"] == 0.6
            return [FakeSegment()], FakeInfo()

    monkeypatch.setattr(transcription, "_load_model", lambda: FakeModel())
    result = transcription.transcribe_audio(
        b"fake audio",
        language="de",
        initial_prompt="contract",
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
    )
    assert result == {"text": "contract clause", "language": "en"}


def test_live_path_passes_pinned_values(monkeypatch):
    captured = {}

    def fake_transcribe(audio_bytes, **kwargs):
        captured.update(kwargs)
        return {"text": "ok", "language": "en"}

    monkeypatch.setattr(transcription, "transcribe_audio", fake_transcribe)
    session_store.create_session("live-kwargs", "")
    live_worker.process_chunk("live-kwargs", 0, b"fake")
    assert captured == {
        "language": settings.LIVE_WHISPER_LANGUAGE,
        "initial_prompt": settings.LIVE_WHISPER_INITIAL_PROMPT,
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.6,
    }


def test_settings_language_de_is_passed(monkeypatch):
    captured = {}

    def fake_transcribe(audio_bytes, **kwargs):
        captured.update(kwargs)
        return {"text": "ok", "language": "de"}

    monkeypatch.setattr(transcription, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(settings, "LIVE_WHISPER_LANGUAGE", "de")
    session_store.create_session("live-de", "")
    live_worker.process_chunk("live-de", 0, b"fake")
    assert captured["language"] == "de"
