# Scope — v1

## What v1 does

1. Manual entry: the lawyer types or pastes a discussion point raised in a meeting.
2. Retrieval: Niyosh retrieves verbatim passages from a selected reference contract (RAG).
3. Output: a compact, cited finding — a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise, labelled "draft — review required".

## What v1 does NOT do

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
- **§ 201 StGB caution** — audio recording in meetings raises criminal-law risk (violation of the confidentiality of the spoken word). Audio capture is deliberately deferred to a later phase behind an explicit consent gate and benchmarks.

Later phases (consent gate, live transcription, advise panel) are documented in `ARCHITECTURE.md`.
