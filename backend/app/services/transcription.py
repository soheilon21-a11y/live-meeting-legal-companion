import os
from io import BytesIO

from app.core.config import settings

ENGINE_MISSING = "Transcription engine not available — install faster-whisper"
MODEL_MISSING = (
    "Whisper model is not provisioned locally. Run scripts/download_models.py "
    "once (with internet) to cache it, then retry. Niyosh never downloads "
    "models automatically."
)

_model = None


class _FakeASR:  # test-only: fixed silent segment, no model download
    def transcribe(self, audio, beam_size=1, **kwargs):
        class _Seg:
            text = ""

        class _Info:
            language = "en"

        return iter([_Seg()]), _Info()


def _fake_asr_enabled() -> bool:
    """Return True only for an explicit test-only opt-in.

    A nonempty string such as ``"0"`` is truthy in Python, so a bare
    ``if os.getenv(...)`` would wrongly activate Fake-ASR. Only an explicit
    positive value enables it; the real application launcher fails closed
    before this code can even run when the variable is present.
    """
    return os.environ.get("NIYOSH_E2E_FAKE_ASR", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _load_model():
    global _model
    if _model is not None:
        return _model
    if _fake_asr_enabled():
        return _FakeASR()  # test-only: no model download
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(ENGINE_MISSING)
    model_dir = settings.WHISPER_MODEL_DIR
    if not model_dir.is_dir() or not (model_dir / "model.bin").exists():
        raise RuntimeError(MODEL_MISSING)
    # Load from the provisioned local directory with local_files_only=True so an
    # upload can never silently initiate a model download.
    _model = WhisperModel(
        str(model_dir),
        device="cpu",
        compute_type="int8",
        local_files_only=True,
    )
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
