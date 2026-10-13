# Scope — v1 + Phase 2

## What it does

1. Manual entry: the lawyer types or pastes a discussion point raised in a meeting.
2. Document ingestion (Phase 2): the lawyer uploads a reference contract (PDF, DOCX, or TXT). Text is extracted locally, chunked, embedded, and stored in a ChromaDB collection scoped to the session.
3. Retrieval: Niyosh retrieves verbatim passages from the uploaded reference contract (RAG, top-3).
4. Analysis (Phase 2): a local LLM (Llama 3 via Ollama) grounds a finding in the retrieved passages.
5. Output: a compact, cited finding — a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise, labelled "draft — review required".
6. Sessions (Phase 2): findings are stored per session, can be exported as PDF, and can be deleted (first-class privacy feature).

## What it does NOT do

- No audio capture.
- No transcription.
- No speaker diarization.
- No text-to-speech.
- No video.
- No autonomous decisions.
- No legal advice.
- No compliance verdicts.

## Why

These limits are a deliberate scope decision:

- **Simplicity Mandate** — ship the smallest honest thing first: retrieval and drafting, nothing more.
- **RDG caution** (German *Rechtsdienstleistungsgesetz*) — the builder is a law graduate, not a licensed attorney. The tool must never be positioned as producing legal advice or autonomous legal work.
- **§ 201 StGB caution** — audio recording in meetings raises criminal-law risk (violation of the confidentiality of the spoken word). Audio capture is deliberately deferred to Phase 3 behind an explicit consent gate and benchmarks.

## Phase status

- **Phase 1 (v1)** — manual entry + retrieval. Shipped.
- **Phase 2** — live analysis of uploaded documents and manually entered discussion points. Shipped (this branch).
- **Phase 3** — audio capture and live transcription. NOT built. Deferred behind a consent gate and benchmarks.

Later phases (consent gate, live transcription, advise panel) are documented in `ARCHITECTURE.md`.
