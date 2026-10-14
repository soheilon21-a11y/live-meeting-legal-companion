# Security & Privacy

## What runs locally

All processing happens on the host machine:

- The FastAPI app runs in a container (port 8002, bound to localhost).
- Ollama runs locally and serves Llama 3.
- ChromaDB stores embeddings and source passages locally.

## What never leaves the machine

No external requests are made at runtime. No telemetry, no analytics, no cloud services. ChromaDB's anonymized telemetry is disabled (`ANONYMIZED_TELEMETRY=False`).

## Data storage

- Chroma data: one collection per session under `backend/data/chroma/` (named volume `data` at `/app/data` in Docker).
- Session metadata, findings, and transcript: JSON files under `backend/data/sessions/<session_id>.json`.
- Consent log: `backend/data/consent.jsonl` (append-only JSONL, see below).
- The website stores nothing: no cookies, no trackers, no browser storage. The only client-side state is the in-memory session ID on the Live page, which is lost on reload.

`backend/data/` is gitignored and never committed.

## Session data retention

Live Analysis stores the following per session:

- **Extracted text chunks** and their embeddings — in a ChromaDB collection named `chroma_<session_id>` under `backend/data/chroma/`.
- **Findings** — each finding (verbatim passage, position, issue question, evidence status, suggested question) is appended to `backend/data/sessions/<session_id>.json`.
- **Session metadata** — the session ID, document filename, and creation time, in the same JSON file.

**Raw uploaded documents are not persisted** beyond their extracted text chunks. The original PDF/DOCX/TXT bytes are held in memory only during upload and are discarded immediately after ingestion. The only way raw document text leaves the session is the explicit "Export findings (PDF)" action, which the user triggers themselves.

## Consent log (consent.jsonl)

Consent is recorded in an **append-only JSONL log** at `backend/data/consent.jsonl`.

- **Append-only, tamper-evident by design:** each consent event is appended as a single JSON line. There is no edit or delete of past entries.
- **Owner-only permissions:** the file is set to `0600` (owner read/write) whenever it is created or written.
- **Deletion (GDPR Art. 17):** `clear_consents(session_id)` removes only that session's lines. This is a deliberate, narrow exception to append-only behaviour to satisfy the right to erasure.
- The consent log is tamper-evident by design, **not a certified legal record.**

## Consent gate (hard technical gate)

Full-meeting audio capture is refused **in code** unless a consent record with `consent_given: true` exists for that session. The backend returns 403 from `POST /api/live/transcribe` without recorded consent — this is enforced by the code, not by policy.

## Dictation-only mode (default)

Dictation-only mode captures only the lawyer's own voice, so no consent from other speakers is required. It is always available in any jurisdiction and is the default; full-meeting capture is opt-in per session.

## Country check (informational)

The country check is **informational only — not legal advice.** The **user is responsible** for verifying local recording laws (e.g. § 201 StGB in Germany) before using audio capture. If recording is restricted or prohibited in the meeting's jurisdiction, the user must disable audio capture before the meeting starts. This responsibility lies with the user, not the builder.

## Text-to-speech (Phase 5a)

TTS audio is generated locally using Piper. No audio data is sent to any external service. Voice models are stored locally (`models/piper/`). TTS output is streamed to the browser and not persisted.

## No certification claims

Niyosh does **not** claim SOC 2, ISO 27001, or any other certification. The local-only, zero-external-request architecture **is** the security claim — everything runs on the host machine and nothing leaves it.

## How to delete data

### In the app

The Live page "Delete session" button calls `DELETE /api/live/session/{session_id}`. This:

1. Removes the ChromaDB collection `chroma_<session_id>` (the text chunks and embeddings).
2. Removes `backend/data/sessions/<session_id>.json` (findings and metadata).

Deletion is immediate and irreversible. No tombstone, no soft delete, no background copy.

### From the filesystem

```bash
# delete a single session's data
rm -rf backend/data/sessions/<session_id>.json
# delete everything (all sessions)
docker compose down -v   # removes the named `data` volume, including all Chroma data and sessions
```

`docker compose down -v` removes the named volume (including `data`). In the container, session data lives at `/app/data` and is persistent only because it is mounted as the `data` volume; without the volume it is lost on container recreation.

## Threat model

Minimal: single-user, local, no network surface.

- The API publishes port 8002 bound to `127.0.0.1` (localhost only).
- There is no multi-tenancy and no remote client trust boundary. CORS is restricted to `localhost`/`127.0.0.1` origins only.
- The main risk is local: someone with filesystem access already has the machine.
- The website is fully static and enforces a strict Content-Security-Policy. All pages use `script-src 'none'`; only the Live page enables a local script (`script-src 'self'`) and allows requests to `http://localhost:8002`.
