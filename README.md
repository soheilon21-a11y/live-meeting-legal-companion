# Niyosh — Live Legal Meeting Companion

A local, privacy-first meeting companion for legal professionals. Niyosh retrieves verbatim passages from a selected reference contract and returns a compact, cited finding so the lawyer can decide what to raise next.

> **v1 in development.** v1 works with manually entered discussion points. NO audio capture, NO transcription — a deliberate scope decision for the first release.

## What it is

- You type or paste a discussion point raised in a meeting.
- Niyosh retrieves verbatim passages from a selected reference contract (RAG).
- It returns a compact, cited finding: a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise — labelled "draft — review required".
- The human legal professional is the sole decision-maker. Niyosh retrieves and drafts; it never decides.

## What it is not (v1)

- No audio capture, no transcription, no speaker diarization, no TTS, no video.
- No autonomous decisions, no legal advice, no compliance verdicts.

These are deferred to later phases behind a consent gate and benchmarks. See `docs/SCOPE.md`.

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

The API listens on http://localhost:8002. Health check at http://localhost:8002/health.

## Provenance

Patterns reused from two shipped sibling tools: **Karnam** (post-meeting-legal-analyzer) and **Namag** (Legal-Clause-Analyzer).

## Privacy

0 external requests · 0 cookies · 0 trackers — enforced by the build and CI.

## License

MIT © 2026 Soheil Onsori
