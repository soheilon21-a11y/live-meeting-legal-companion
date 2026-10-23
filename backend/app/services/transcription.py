import os
from io import BytesIO

from app.core.config import settings

ENGINE_MISSING = "Transcription engine not available — install faster-whisper"

_model = None


class _FakeASR:  # test-only: fixed silent segment, no model download
    def transcribe(self, audio, beam_size=1, **kwargs):
        class _Seg:
            text = ""

        class _Info:
            language = "en"

        return iter([_Seg()]), _Info()


def _load_model():
    global _model
    if _model is not None:
        return _model
    if os.getenv("NIYOSH_E2E_FAKE_ASR"):
        return _FakeASR()  # test-only: no model download
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(ENGINE_MISSING)
    _model = WhisperModel(settings.LIVE_WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(
    file_bytes: bytes,
    language: str | None = None,
    initial_prompt: str | None = None,
    condition_on_previous_text: bool | None = None,
    no_speech_threshold: float | None = None,
) -> dict:
    model = _load_model()
    kwargs = {}
    if language is not None:
        kwargs["language"] = language
    if initial_prompt is not None:
        kwargs["initial_prompt"] = initial_prompt
    if condition_on_previous_text is not None:
        kwargs["condition_on_previous_text"] = condition_on_previous_text
    if no_speech_threshold is not None:
        kwargs["no_speech_threshold"] = no_speech_threshold
    segments, info = model.transcribe(
        BytesIO(file_bytes), beam_size=settings.LIVE_WHISPER_BEAM_SIZE, **kwargs
    )
    text = "".join(segment.text for segment in segments).strip()
    return {"text": text, "language": info.language}
