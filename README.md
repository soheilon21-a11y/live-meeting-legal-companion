# Niyosh — Live Legal Meeting Companion

A local, privacy-first meeting companion for legal professionals. Niyosh retrieves verbatim passages from a reference contract and returns a compact, cited finding so the lawyer can decide what to raise next.

> **v1 in development.** No audio capture, no transcription — a deliberate scope decision. Live analysis works with manually entered discussion points and an uploaded reference contract.

## What it is

- **Live Analysis (Phase 2):** upload a reference contract (PDF/DOCX/TXT) and type a discussion point raised in the meeting.
- Niyosh ingests the document locally, retrieves verbatim passages (RAG), and grounds a finding in them with a local LLM (Llama 3 via Ollama).
- It returns a compact, cited finding: a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise — labelled "draft — review required".
- Findings are kept in a per-session history, can be exported as PDF, and can be deleted at any time.
- The human legal professional is the sole decision-maker. Niyosh retrieves and drafts; it never decides.

## What it is not

- No audio capture, no transcription, no speaker diarization, no TTS, no video.
- No autonomous decisions, no legal advice, no compliance verdicts.
- No cloud, no paid APIs, no telemetry — everything runs on your machine.

Audio capture and transcription are deferred to Phase 3 behind a consent gate and benchmarks. See `docs/SCOPE.md`.

## Stack

- FastAPI + Uvicorn (API)
- Ollama (Llama 3, local inference)
- ChromaDB + sentence-transformers (RAG)
- Docker Compose
- pytest + GitHub Actions (CI)
- Astro static site (EN/DE)

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
