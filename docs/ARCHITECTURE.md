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
4. **Automatic observations (Phase 4b):** while recording, the page polls `/observations?since=<last_chunk_index>` every 10 seconds → `observer.check_recent_transcript` reads only the new transcript entries and retrieves the top-3 passages (K=3) → a new observation is stored in `data/observations/<session_id>.json` and rendered as a non-blocking, dismissible card.

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
- `app/services/observation_store.py` — per-session JSON observation store (`data/observations/<session_id>.json`): add / get / dismiss (dismiss marks `dismissed=true`, never deletes).
- `app/services/observer.py` — `check_recent_transcript(session_id, since_index, document_id)`: reads only new transcript entries (`chunk_index > since_index`), caps the excerpt at ~2000 chars, runs retrieval (K=3), and returns at most one retrieval-based observation (no LLM call).

## Live transcription worker (Phase 4a)

Live audio is transcribed by a single background thread:

- `queue.Queue(maxsize=LIVE_MAX_QUEUE)` holds pending chunks; the endpoint enqueues and returns immediately, so the browser is never blocked.
- A `threading.Thread` (daemon) dequeues chunks one at a time and calls `transcription.transcribe_audio`, then appends the result to the session transcript (`mode: "live"`).
- A module-level `threading.Lock` (`model_lock`) is shared with `analysis.analyze` so ASR and the LLM never run concurrently (8 GB RAM constraint).
- If the queue is full, new chunks are saved to disk and tracked as a **backlog**, reported by the status endpoint and drained on `stop`.

## Automatic observations (Phase 4b)

Observations are **non-blocking review prompts** generated while the meeting is transcribed:

- The frontend tracks the last processed `chunk_index` and polls `GET /observations?since=<index>&document_id=<id>` every 10 seconds during recording (plus once after upload). The backend is stateless — the frontend owns the cursor.
- `observer.check_recent_transcript` concatenates only the **new** transcript text (`chunk_index > since`), capped at ~2000 chars, and runs `retrieval.retrieve(document_id, excerpt, k=3)`. No LLM call — deterministic and local.
- If a passage is retrieved, one observation is built (issue phrased as a question, `evidence_status: "supported"`, the triggering excerpt) and persisted via `observation_store.add_observation`.
- If no passage is relevant (or the excerpt is too short), no observation is created, but the returned `last_index` still advances so the same text is never re-checked.
- Dismissal is a `POST /observations/{obs_id}/dismiss` that marks the record `dismissed=true` (audit trail) — it is never deleted.

## Audio capture modes (Phase 3)

- **Dictation-only (default):** captures only the lawyer's own voice. Always available, no consent from others required.
- **Full-meeting capture (opt-in):** requires a Country Check and recorded collective consent for the session. The backend refuses capture in code (`403`) without a consent record.

The country check is informational only, not legal advice (see `SCOPE.md` and `SECURITY.md`).
