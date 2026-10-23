Known Issues Ledger — Niyosh

Living list of accepted, documented limitations. Each item is a conscious deferral, not an unnoticed bug. Discipline: diagnose, then judge, then fix.



L1 — append_transcript has no lock (race)

session_store.append_transcript does read-modify-write on the session JSON without a lock; concurrent writes can lose entries. This is not hypothetical: cross-thread read-modify-write happens today — the live-worker daemon and the uvicorn threadpool both mutate the same session JSON via /transcribe, /dictation, /diarize, /correct-speaker, and /analyze.

Status: FIXED — f8f8ce2 (session-store RLock; regression test added).



L2 — /transcribe and /dictation bypass model_lock

File-based endpoints call transcription without model_lock, so ASR and the LLM could run concurrently on the 8 GB constraint. Live path is protected; file path is not.

Status: FIXED — 1fe21f0 (file transcription serialized through model_lock).



L3 — No browser-level E2E test

pytest covers backend logic; no automated browser test exercises the live.js recording flow (MediaRecorder behavior is the risk area).

Status: OPEN.



L4 — live.js hides empty-text transcript segments

pollTranscript (live.js:580-581) drops any chunk whose trimmed text is empty. A chunk that transcribes to "" is not rendered and can mimic a second failure. Observability fix, deferred.

Status: FIXED — b15fb93 (empty segments render a bracketed placeholder).



L5 — Recorder rebuild ignores dead tracks (plus latent stopRecording hang)

(a) In mediaRecorder.onstop, a new recorder is created whenever sessionActive && mediaStream, even if all audio tracks are dead (mic unplugged), which can loop error states. One-line future guard: mediaStream.getTracks().some(t => t.readyState === "live").

(b) Latent hang: stopRecording (live.js:672-676) awaits the onstop promise even when the recorder is already inactive, so the promise never resolves and the UI deadlocks.

Status: FIXED — b81a1e3 (dead-track stop + inactive-stop await guard).



L6 — "Disable audio capture" does not gate the Live Meeting recorder (design)

Found: 2026-10-23, manual UI acceptance test (post-1f344c0). Repro: tick "Disable audio capture for this session" → the Audio (file-analysis) section below hides as documented, but Live Meeting stays active; "Start recording" still enters Recording state. Impact: Control/Privacy gap — the switch promises to disable capture for the session but only hides file-analysis controls. NOT a consent bypass: full-meeting mode still requires recorded consent (403 gate verified) and audio stays local. Ruling (2026-10-23): client-side enforcement this round (hide/disable Live Meeting controls, orderly-stop an in-progress recording when ticked); server-side capture-disabled flag deferred as L8.

Status: FIXED — 4faf62b (client-side enforcement; server side deferred to L8).



L7 — /diarize runs SpeechBrain diarization without model_lock

Diarization loads a third heavy model and runs CPU-bound inference outside model_lock, the same 8 GB invariant as L2. ASR, LLM, and diarization should never run concurrently.

Status: FIXED — 8d5d0d1 (diarization serialized through model_lock).



L8 — No server-side capture-disabled enforcement (defense in depth)

A capture-disabled flag would let /chunk, /transcribe, and /dictation reject uploads (409) for a capture-disabled session. Deferred by the L6 ruling (client-side only this round).

Status: OPEN (deferred by ruling).



L9 — analysis.py logs raw LLM output on degenerate responses

analysis.py:102-104 logs raw[:200] of degenerate LLM output. That output may contain transcript-derived text or retrieved-passage text, so logging it leaks content into the logs (privacy).

Status: FIXED — fab4cfa (degenerate-output log redacted to length).



Backlog (separate from ledger)

Whisper language lock + legal-vocabulary initial_prompt for live mode.

Accepted trade-off (commit 1f344c0): millisecond audio gap at slice boundaries from per-slice MediaRecorder recreation.
