# Architecture

## Current stack (v1)

- FastAPI (Python 3.12) — API layer.
- Ollama — local LLM inference (Llama 3).
- ChromaDB + sentence-transformers — retrieval (embeddings + vector search).
- Docker Compose — two services (`app` + `ollama`) and one named `chroma_data` volume.
- Astro — static bilingual (EN/DE) site.
- pytest + GitHub Actions — CI.

## Data flow (v1)

Manual entry → verbatim retrieval (RAG) → cited finding ("draft — review required").

## Components added in later phases (NOT built in v1)

All three are deferred to Phase 2+ behind a consent gate and benchmarks:

1. **Consent gate** — explicit, recorded consent before any audio feature.
2. **Live transcription** — real-time speech-to-text.
3. **Advise panel** — in-meeting suggestions.

## Decision: not built in v1

v1 ships retrieval and drafting only. Audio capture, transcription, and in-meeting advising are deliberately excluded to keep the first release small, honest, and legally cautious (RDG and § 201 StGB — see `SCOPE.md`).
