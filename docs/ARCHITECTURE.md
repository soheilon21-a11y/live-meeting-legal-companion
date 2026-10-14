# Architecture

## Current stack

- FastAPI (Python 3.12) — API layer.
- Ollama — local LLM inference (Llama 3).
- ChromaDB + sentence-transformers — retrieval (embeddings + vector search).
- faster-whisper (optional) — local, CPU speech-to-text for audio capture.
- Docker Compose — two services (`app` + `ollama`) and one named `data` volume.
- Astro — static bilingual (EN/DE) site.
- pytest + GitHub Actions — CI.

## Data flow

1. **Live analysis (Phase 2):** upload a reference contract → ingest (extract text, chunk, embed) → manual discussion point → verbatim retrieval (RAG) → LLM-grounded, cited finding ("draft — review required").
2. **Audio capture (Phase 3):** dictation-only mode (default) or full-meeting capture (opt-in, behind a country check + hard consent gate) → local transcription (faster-whisper) → transcript appended to the session → transcript may feed `transcript_excerpt` into retrieval context.
3. **Live transcription (Phase 4a):** browser `MediaRecorder` captures 15-second chunks → `POST /chunk` (saved to disk, then enqueued) → background worker transcribes each chunk → the page polls `/transcript/live` for new entries.

## Services

- `app/services/ingest.py` — extract text (PDF/DOCX/TXT), chunk, embed, store in Chroma.
- `app/services/retrieval.py` — embed the query and return the top-K verbatim passages.
- `app/services/analysis.py` — build the LLM prompt, call Ollama, parse and validate the finding (with a retrieval-only fallback).
- `app/services/chroma_store.py` — Chroma collection lifecycle (get / create / delete per session).
- `app/services/embedding.py` — sentence-transformers embedding helper.
- `app/services/session_store.py` — per-session JSON: metadata, findings, and transcript.
- `app/services/consent_store.py` — append-only JSONL consent log (`data/consent.jsonl`), owner-only permissions, GDPR erasure.
- `app/services/country_check.py` — static, informational recording-rules lookup per country.
- `app/services/transcription.py` — faster-whisper (local, CPU) batch transcription with a graceful error if not installed.
- `app/services/live_worker.py` — background live-transcription worker (see below).

## Live transcription worker (Phase 4a)

Live audio is transcribed by a single background thread:

- `queue.Queue(maxsize=LIVE_MAX_QUEUE)` holds pending chunks; the endpoint enqueues and returns immediately, so the browser is never blocked.
- A `threading.Thread` (daemon) dequeues chunks one at a time and calls `transcription.transcribe_audio`, then appends the result to the session transcript (`mode: "live"`).
- A module-level `threading.Lock` (`model_lock`) is shared with `analysis.analyze` so ASR and the LLM never run concurrently (8 GB RAM constraint).
- If the queue is full, new chunks are saved to disk and tracked as a **backlog**, reported by the status endpoint and drained on `stop`.

## Audio capture modes (Phase 3)

- **Dictation-only (default):** captures only the lawyer's own voice. Always available, no consent from others required.
- **Full-meeting capture (opt-in):** requires a Country Check and recorded collective consent for the session. The backend refuses capture in code (`403`) without a consent record.

The country check is informational only, not legal advice (see `SCOPE.md` and `SECURITY.md`).
