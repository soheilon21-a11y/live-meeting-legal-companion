Known Issues Ledger — Niyosh

Living list of accepted, documented limitations. Each item is a consciousdeferral, not an unnoticed bug. Discipline: diagnose, then judge, then fix.



L1 — append\_transcript has no lock (race)

session\_store.append\_transcript does read-modify-write on the session JSONwithout a lock; concurrent writes can lose entries. Low likelihood today(single worker per session), real risk if concurrency grows.



L2 — /transcribe and /dictation bypass model\_lock

File-based endpoints call transcription without model\_lock, so ASR and theLLM could run concurrently on the 8 GB constraint. Live path is protected;file path is not.



L3 — No browser-level E2E test

pytest covers backend logic; no automated browser test exercises the live.jsrecording flow (MediaRecorder behavior is the risk area).



L4 — live.js hides empty-text transcript segments (\~line 573)

A chunk that transcribes to "" is not rendered and can mimic a secondfailure. Observability fix, deferred.



L5 — Recorder rebuild ignores dead tracks

In mediaRecorder.onstop, a new recorder is created wheneversessionActive \&\& mediaStream, even if all audio tracks are dead (micunplugged), which can loop error states. One-line future guard:mediaStream.getTracks().some(t => t.readyState === "live").



L6 — "Disable audio capture" does not gate the Live Meeting recorder (design)

Found: 2026-10-23, manual UI acceptance test (post-1f344c0).Repro: tick "Disable audio capture for this session" → the Audio(file-analysis) section below hides as documented, but Live Meeting staysactive; "Start recording" still enters Recording state.Impact: Control/Privacy gap — the switch promises to disable capture for thesession but only hides file-analysis controls. NOT a consent bypass:full-meeting mode still requires recorded consent (403 gate verified) andaudio stays local.Fix options: (a) honest copy — reword the toggle; (b) enforce — hide/disableLive Meeting controls, stop in-progress recording if ticked mid-session, andreject chunk uploads server-side for capture-disabled sessions; (c) both.Priority: medium-low — decide design intent first.



Backlog (separate from ledger)

Whisper language lock + legal-vocabulary initial\_prompt for live mode.

Accepted trade-off (commit 1f344c0): millisecond audio gap at sliceboundaries from per-slice MediaRecorder recreation.

