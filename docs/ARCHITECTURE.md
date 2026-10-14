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
5. **Speaker diarization (Phase 4c):** after the meeting, `POST /diarize` reads the stored `chunk_*.webm` files, extracts one SpeechBrain ECAPA-TDNN embedding per chunk, clusters them with scikit-learn `AgglomerativeClustering` (cosine affinity), and writes a `speaker` label onto each transcript entry matched by `chunk_index`. The user can override any label via `POST /correct-speaker`.
6. **Text-to-speech (Phase 5a):** the page sends a finding's text (plus a `lang`) to `POST /session/{id}/speak`; `tts.speak` synthesizes it with the local Piper voice and returns WAV bytes, which the browser plays. Audio is streamed and never stored. This only reads existing findings — the RAG/LLM pipeline is untouched.

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
- `app/services/diarization.py` — speaker diarization: one SpeechBrain ECAPA-TDNN embedding per stored audio chunk, clustered with scikit-learn `AgglomerativeClustering` (cosine affinity, `distance_threshold` for 2-6 speakers, or a user-specified speaker count), then mapped to "Speaker N" labels in order of first appearance. Gracefully errors if `speechbrain`/`scikit-learn` are missing, if fewer than 2 chunks exist, or if the model cannot be downloaded.
- `app/services/tts.py` — local text-to-speech with Piper (CPU, offline). A lazy singleton loads one voice model per language (EN: `en_US-lessac-medium`, DE: `de_DE-thorsten-medium`) from `models/piper/` and reuses it. `speak(text, lang)` returns WAV bytes; unsupported languages fall back to EN, input is truncated at ~500 chars, and a clear error is raised if `piper-tts` or the voice model is missing.

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

## Speaker diarization (Phase 4c)

Diarization is **post-meeting and user-initiated** — it never runs automatically and never triggers new audio capture:

- `POST /api/live/session/{session_id}/diarize` (optional JSON body `{"expected_speakers": 2..6}`; empty for auto-estimate) reads `data/audio/<session_id>/chunk_*.webm`, extracts one embedding per chunk, clusters them, and writes a `speaker` label onto each transcript entry whose `chunk_index` matches a chunk. Returns `speakers_detected` and the updated transcript.
- `POST /api/live/session/{session_id}/correct-speaker` (`{"chunk_index": N, "speaker": "..."}`) overwrites a single label — the manual-correction audit trail.
- One label per 15-second chunk (not per utterance) — an honest approximation disclosed in the UI.
- Runs on already-captured, consent-gated audio; no cloud, no paid APIs.

## Audio capture modes (Phase 3)

- **Dictation-only (default):** captures only the lawyer's own voice. Always available, no consent from others required.
- **Full-meeting capture (opt-in):** requires a Country Check and recorded collective consent for the session. The backend refuses capture in code (`403`) without a consent record.

The country check is informational only, not legal advice (see `SCOPE.md` and `SECURITY.md`).

## Text-to-speech (Phase 5a)

TTS is a read-only audio output of existing findings — it never modifies the RAG or LLM flow.

- `POST /api/live/session/{session_id}/speak` accepts `{"text": "...", "lang": "en"|"de"}`, validates non-empty text and session existence (404/400), then calls `tts.speak`. Returns `audio/wav` bytes with a `X-Audio-Truncated` header when the input exceeded ~500 characters.
- Piper runs locally on CPU inside the app container; voice models (`en_US-lessac-medium`, `de_DE-thorsten-medium`) live in `models/piper/` and are downloaded once via `scripts/download_models.py`.
- If `piper-tts` is not installed or a voice model is missing, the endpoint returns `503` with a clear message. Audio is streamed and not persisted.
