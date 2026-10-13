from io import BytesIO

from app.core.config import settings

ENGINE_MISSING = "Transcription engine not available — install faster-whisper"

_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(ENGINE_MISSING)
    _model = WhisperModel(settings.LIVE_WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(file_bytes: bytes) -> dict:
    model = _load_model()
    segments, info = model.transcribe(BytesIO(file_bytes), beam_size=5)
    text = "".join(segment.text for segment in segments).strip()
    return {"text": text, "language": info.language}
