import os
from pathlib import Path

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


class Settings:
    APP_NAME = "Niyosh — Live Legal Meeting Companion"
    VERSION = "0.1.0"
    PORT = 8002

    MODEL_NAME = "llama3"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    CHROMA_DATA_DIR = Path(os.getenv("CHROMA_DATA_DIR", "chroma_data"))

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


settings = Settings()
