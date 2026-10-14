# Niyosh — Live Legal Meeting Companion

A local, privacy-first meeting companion for legal professionals. Niyosh retrieves verbatim passages from a reference contract and returns a compact, cited finding so the lawyer can decide what to raise next. It also captures and transcribes meeting audio locally, behind a consent gate.

## What it is

- **Live Analysis:** upload a reference contract (PDF/DOCX/TXT) and type a discussion point raised in the meeting.
- Niyosh ingests the document locally, retrieves verbatim passages (RAG), and grounds a finding in them with a local LLM (Llama 3 via Ollama).
- It returns a compact, cited finding: a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise — labelled "draft — review required".
- Findings are kept in a per-session history, can be exported as PDF, and can be deleted at any time.
- **Audio capture (Phase 3):** two modes — see below.
- **Live Meeting (Phase 4a):** record the meeting and see a live transcript with a 30-90 second delay — two modes: dictation-only (always available) and full meeting (consent required).
- The human legal professional is the sole decision-maker. Niyosh retrieves and drafts; it never decides.

## Audio capture (Phase 3)

Audio capture is available in two modes:

- **Dictation-only (default, always available).** Captures only the lawyer's own voice — no consent from other speakers needed, in any jurisdiction.
- **Full-meeting capture (opt-in per session).** Captures all speakers. Requires a **Country Check** (informational recording-rules summary) and **recorded collective consent** for that session. Without recorded consent the backend refuses audio capture in code.

> The country check is **informational only — not legal advice.** The user is responsible for verifying local recording laws (e.g. § 201 StGB in Germany) before using audio capture. See `docs/SCOPE.md` and `docs/SECURITY.md`.

## Live Meeting (Phase 4a)

Record the meeting from the Live page and watch a live transcript appear — with a 30-90 second delay (this is normal; transcription is near-real-time, not streaming). Two modes:

- **Dictation only (my voice — always available).** No consent required.
- **Full meeting (all voices — consent required).** The backend refuses capture (`403`) without recorded consent for the session.

Audio is captured in 15-second chunks, saved to disk first, then transcribed sequentially by a single background worker. Raw audio is never deleted automatically — you decide via the existing delete-session action.

## What it is not

- No speaker diarization, no real-time streaming transcription (live transcription is chunked, 30-90 s delay), no TTS, no video.
- No autonomous decisions, no legal advice, no compliance verdicts.
- No cloud, no paid APIs, no telemetry — everything runs on your machine.

## Stack

- FastAPI + Uvicorn (API)
- Ollama (Llama 3, local inference)
- ChromaDB + sentence-transformers (RAG)
- faster-whisper (optional, local CPU speech-to-text)
- Docker Compose
- pytest + GitHub Actions (CI)
- Astro static site (EN/DE)

## Optional: enable transcription

Transcription uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper), which is **not** included in `requirements.txt` (heavy — it downloads a model on first run). Install it separately:

```bash
pip install faster-whisper
```

Without it, transcription endpoints return a clear error: "Transcription engine not available — install faster-whisper". The model size is configurable via the `LIVE_WHISPER_MODEL` env var (default `small`).

## Quickstart

```bash
docker compose up
```

Then open the Live page:

- English: http://localhost:4321/live/
- Deutsch: http://localhost:4321/de/live/

The API listens on http://localhost:8002. Health check at http://localhost:8002/health.

## Privacy

0 external requests · 0 cookies · 0 trackers — enforced by the build and CI. See `docs/SECURITY.md`.

## Provenance

Patterns reused from two shipped sibling tools: **Karnam** (post-meeting-legal-analyzer) and **Namag** (Legal-Clause-Analyzer).

## License

MIT © 2026 Soheil Onsori
