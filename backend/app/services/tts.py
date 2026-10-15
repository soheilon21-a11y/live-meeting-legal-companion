import os
import wave
from io import BytesIO
from pathlib import Path

ENGINE_MISSING = (
    "TTS engine not available — install piper-tts and download the voice models "
    "via scripts/download_models.py"
)
EMPTY_TEXT = "Text is empty — nothing to speak"

MAX_CHARS = 500

EN_VOICE = "en_US-lessac-medium"
DE_VOICE = "de_DE-thorsten-medium"

_REPO_ROOT = Path(__file__).resolve().parents[3]
PIPER_MODEL_DIR = Path(os.getenv("PIPER_MODEL_DIR", str(_REPO_ROOT / "models" / "piper")))

_voices = {}


def _voice_name(lang: str) -> str:
    return DE_VOICE if (lang or "").lower() == "de" else EN_VOICE


def _load_voice(lang: str):
    voice_name = _voice_name(lang)
    if voice_name in _voices:
        return _voices[voice_name]
    try:
        from piper import PiperVoice
    except ImportError:
        raise RuntimeError(ENGINE_MISSING)
    model_path = PIPER_MODEL_DIR / f"{voice_name}.onnx"
    if not model_path.exists():
        raise RuntimeError(ENGINE_MISSING)
    _voices[voice_name] = PiperVoice.load(str(model_path))
    return _voices[voice_name]


def speak(text: str, lang: str = "en") -> bytes:
    text = (text or "").strip()
    if not text:
        raise ValueError(EMPTY_TEXT)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rstrip() + "…"
    voice = _load_voice(lang)
    buf = BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    return buf.getvalue()
