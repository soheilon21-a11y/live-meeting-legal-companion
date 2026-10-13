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
- Session metadata and findings: JSON files under `backend/data/sessions/<session_id>.json`.
- The website stores nothing: no cookies, no trackers, no browser storage. The only client-side state is the in-memory session ID on the Live page, which is lost on reload.

`backend/data/` is gitignored and never committed.

## Session data retention

Live Analysis stores the following per session:

- **Extracted text chunks** and their embeddings — in a ChromaDB collection named `chroma_<session_id>` under `backend/data/chroma/`.
- **Findings** — each finding (verbatim passage, position, issue question, evidence status, suggested question) is appended to `backend/data/sessions/<session_id>.json`.
- **Session metadata** — the session ID, document filename, and creation time, in the same JSON file.

**Raw uploaded documents are not persisted** beyond their extracted text chunks. The original PDF/DOCX/TXT bytes are held in memory only during upload and are discarded immediately after ingestion. The only way raw document text leaves the session is the explicit "Export findings (PDF)" action, which the user triggers themselves.

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
