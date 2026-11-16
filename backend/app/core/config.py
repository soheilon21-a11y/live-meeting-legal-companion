import os
from pathlib import Path

# ChromaDB anonymized telemetry must be disabled before Chroma is initialized.
# Use an explicit assignment (not ``setdefault``) so a pre-existing value in the
# environment cannot silently re-enable telemetry.
os.environ["ANONYMIZED_TELEMETRY"] = "False"

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings:
    APP_NAME = "Niyosh — Live Legal Meeting Companion"
    VERSION = "0.1.0"
    PORT = 8002

    MODEL_NAME = "llama3"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    # Local model cache, provisioned once by ``scripts/download_models.py``.
    # The runtime loads models from these exact directories and never triggers a
    # download on demand (see transcription.py / embedding.py offline controls).
    MODELS_DIR = Path(os.getenv("NIYOSH_MODELS_DIR", str(_REPO_ROOT / "models")))
    WHISPER_MODEL_DIR = Path(
        os.getenv("WHISPER_MODEL_DIR", str(MODELS_DIR / "faster-whisper-small"))
    )
    EMBEDDING_MODEL_DIR = Path(
        os.getenv("EMBEDDING_MODEL_DIR", str(MODELS_DIR / "all-MiniLM-L6-v2"))
    )

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
    TOP_K = 3

    LIVE_WHISPER_MODEL = os.getenv("LIVE_WHISPER_MODEL", "small")
    LIVE_WHISPER_BEAM_SIZE = int(os.getenv("LIVE_WHISPER_BEAM_SIZE", "1"))
    LIVE_CHUNK_SECONDS = int(os.getenv("LIVE_CHUNK_SECONDS", "15"))
    LIVE_MAX_QUEUE = int(os.getenv("LIVE_MAX_QUEUE", "3"))
    LIVE_WHISPER_LANGUAGE = os.getenv("LIVE_WHISPER_LANGUAGE", "en")
    LIVE_WHISPER_INITIAL_PROMPT = os.getenv(
        "LIVE_WHISPER_INITIAL_PROMPT",
        "contract, clause, termination, liability, indemnity, warranty, jurisdiction, "
        "plaintiff, defendant, hearing, deposition, arbitration, breach, damages, "
        "notice, dispute, evidence, testimony, appeal, statute, compliance",
    )

    # Local LLM (Ollama) generation controls.
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
    LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


settings = Settings()
