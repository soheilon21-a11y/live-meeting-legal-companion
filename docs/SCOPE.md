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

## What Phase 4a adds (live chunked transcription)

The Live page now records the meeting directly in the browser and streams it to the backend in **15-second chunks** (`MediaRecorder`, WebM/Opus). A single background worker thread transcribes each chunk sequentially with local faster-whisper and appends the result to the session transcript, which the page polls every 3 seconds.

- **Two recording modes:** "Full meeting (all voices — consent required)" is refused in code (`403`) without recorded consent for the session; "Dictation only (my voice — always available)" requires no consent.
- **Honest latency label:** transcription is **near-real-time, not real-time** — the page shows a permanent note that transcription appears with a **30-90 second delay** (this is normal).
- **Graceful degradation:** the transcription queue is bounded (max 3). If it fills up, new audio chunks are still saved to disk but deferred to "process after meeting" and the status reports a backlog.
- **Mutual exclusion:** speech-to-text and the LLM share a lock so the two CPU-bound models never run concurrently on the 8 GB RAM target.

## What Phase 4b adds (automatic observations during the meeting)

While the meeting is being transcribed, Niyosh periodically checks the **new** transcript text (only since the last check — never the whole transcript) against the uploaded reference contract using the existing retrieval pipeline (`retrieval.retrieve`, K=3). If a relevant passage is found, a small **observation card** appears in a non-blocking "Observations" panel beside the transcript.

- **Non-blocking:** observations appear in a sidebar section and never interrupt the meeting UI.
- **Review prompts, not conclusions:** each observation is phrased as a **question**, labelled **"auto — review required"**, with an evidence status and a suggested question. Niyosh never decides; the lawyer dismisses or acts.
- **Traceable:** every observation links to the verbatim transcript excerpt that triggered it plus the retrieved contract passage.
- **Auditable:** observations are stored locally in per-session JSON (`data/observations/<session_id>.json`). Dismissing an observation marks it `dismissed=true` for the audit trail — it is never deleted.
- **Deterministic and local:** the check is retrieval-only (no LLM call); it reuses the existing RAG and makes no external requests.

## What Phase 4c adds (speaker diarization)

After a meeting, the user can run **speaker attribution** over the session's already-captured audio chunks. Each 15-second chunk is assigned a single speaker label ("Speaker 1", "Speaker 2", ...) using local SpeechBrain ECAPA-TDNN speaker embeddings clustered with scikit-learn `AgglomerativeClustering` (cosine affinity).

- **Approximate by design:** one label per **chunk** (≈15 s), not per utterance. If two speakers alternate within a single chunk, only the dominant voice is labelled. Labels are honestly disclosed as approximate.
- **Manual correction:** the user can override any entry's speaker label (dropdown, or "Unknown") — the human decides, never the tool.
- **Privacy-preserving:** diarization runs only on audio that was already captured behind the Phase 3 consent gate; it makes no new capture and no external requests. Raw audio is never deleted automatically.
- **Local & sanctions-safe:** SpeechBrain ECAPA-TDNN is Apache-2.0 and ungated (no HuggingFace gating).

## What Phase 5a adds (text-to-speech with Piper)

The Live page can now **read findings aloud** using local Piper TTS (EN + DE voices). A "Read aloud" button appears on each finding card and next to the session findings summary; a voice selector (auto / English / German) lets the user pick the voice, with "auto" detecting the finding's language.

- **100% local:** Piper runs on-CPU inside the existing app container. No cloud, no external requests. TTS audio is streamed straight to the browser and **never persisted** (data minimization).
- **Honest audio:** the voice is synthetic and approximate. The spoken text is the same verbatim finding shown on the page ("what you hear is what you read"), with the "Not legal advice" disclaimer appended. No studio-quality claims.
- **Traceable & auditable:** the endpoint accepts only the finding text plus a language code; it truncates input at ~500 characters for audio-length management. The endpoint is testable — tests cover valid input, empty input, unsupported language, and engine-unavailable.
- **Graceful degradation:** if Piper (or a voice model) is missing, the endpoint returns `503` with a clear "install piper-tts" message, shown to the user.
- **Practical deployment:** voice models are small (~30-100 MB each) and downloaded **once** via `scripts/download_models.py` (`models/piper/`); `docker compose up` remains the entire install story. No new Docker services.

## What v1 / Phase 3 / Phase 4a / Phase 4b / Phase 4c / Phase 5a do NOT do

- No real-time streaming transcription — live transcription is chunked, near-real-time (30-90 s delay), not streaming.
- No video.
- No autonomous decisions.
- No legal advice.
- No compliance verdicts.

## Why

- **Simplicity Mandate** — ship the smallest honest thing first.
- **RDG caution** (German *Rechtsdienstleistungsgesetz*) — the builder is a law graduate, not a licensed attorney. The tool must never be positioned as producing legal advice or autonomous legal work.
- **§ 201 StGB caution** — audio recording in meetings raises criminal-law risk (violation of the confidentiality of the spoken word). Full-meeting capture is therefore opt-in per session, behind a country check and a hard consent gate; dictation-only mode is the always-safe default.

See `ARCHITECTURE.md` for component details and `SECURITY.md` for storage and consent-log handling.
