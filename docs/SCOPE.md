# Scope

## What v1 does

1. Manual entry: the lawyer types or pastes a discussion point raised in a meeting.
2. Retrieval: Niyosh retrieves verbatim passages from a selected reference contract (RAG).
3. Output: a compact, cited finding — a passage, a narrowly stated issue as a question, an evidence status (supported / conflicting / insufficient), and a suggested question to raise, labelled "draft — review required".

## What Phase 3 adds (audio capture + transcription)

Audio capture and transcription are now available, guarded by a **hard technical consent gate**:

- **Dictation-Only Mode (default, always available).** Only the lawyer's own voice is captured. No consent from other speakers is required, in any jurisdiction.
- **Full-Meeting Capture (opt-in per session).** Captures all speakers' audio. This is available **only** after (a) a Country Check and (b) recorded collective consent for that session. Without recorded consent, the backend refuses audio capture in code.

### Country Check

Before full-meeting capture, the user selects the **country of the meeting**. Niyosh displays a summary of recording rules in that country, whether collective consent is sufficient, and a warning: *"Before using this feature in this country, consult a local legal professional."*

The country check is **informational only — not legal advice**. For countries whose rules Niyosh cannot verify, it says: *"Consult a local legal professional before using audio capture in this country."*

### § 201 StGB warning (Germany)

Recording non-public spoken words without the consent of **all speakers** is a criminal offense in Germany (§ 201 StGB). Consent of the parties may resolve **civil** liability but **cannot override criminal liability** in jurisdictions where recording law is mandatory law (jus cogens). The **user is responsible** for verifying local recording laws before using audio capture. If recording is restricted or prohibited in the meeting's jurisdiction, the user must disable audio capture before the meeting starts. This responsibility lies with the user, not the builder.

## What v1 / Phase 3 do NOT do

- No speaker diarization.
- No real-time streaming transcription (batch only).
- No text-to-speech.
- No video.
- No autonomous decisions.
- No legal advice.
- No compliance verdicts.

## Why

- **Simplicity Mandate** — ship the smallest honest thing first.
- **RDG caution** (German *Rechtsdienstleistungsgesetz*) — the builder is a law graduate, not a licensed attorney. The tool must never be positioned as producing legal advice or autonomous legal work.
- **§ 201 StGB caution** — audio recording in meetings raises criminal-law risk (violation of the confidentiality of the spoken word). Full-meeting capture is therefore opt-in per session, behind a country check and a hard consent gate; dictation-only mode is the always-safe default.

See `ARCHITECTURE.md` for component details and `SECURITY.md` for storage and consent-log handling.
