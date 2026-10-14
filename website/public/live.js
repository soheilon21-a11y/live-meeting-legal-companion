const root = document.querySelector(".live");
const I18N = root.dataset;
const API = "http://localhost:8002";
let sessionId = null;
let transcript = [];
const $ = (id) => document.getElementById(id);
const fileInput = $("live-file"), pointInput = $("live-point"), analyzeBtn = $("live-analyze");
const statusEl = $("live-status"), resultEl = $("live-result"), findingsEl = $("live-findings");
const exportBtn = $("live-export"), deleteBtn = $("live-delete");
const countrySelect = $("live-country"), countryInfo = $("live-country-info");
const participantsInput = $("live-participants"), consentCheck = $("live-consent");
const recordConsentBtn = $("live-record-consent"), consentStatus = $("live-consent-status");
const disableAudio = $("live-disable-audio"), audioControls = $("live-audio-controls");
const audioFileInput = $("live-audio-file"), transcribeBtn = $("live-transcribe");
const viewTranscriptBtn = $("live-view-transcript"), audioStatus = $("live-audio-status");
const transcriptWrap = $("live-transcript-wrap"), transcriptList = $("live-transcript");
const copyToPointBtn = $("live-copy-to-point");

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
const badges = { supported: [I18N.evSupported, "badge-supported"], conflicting: [I18N.evConflicting, "badge-conflicting"], insufficient: [I18N.evInsufficient, "badge-insufficient"] };
function badge(s) {
  const [label, cls] = badges[s] || [s, "badge-insufficient"];
  return el("span", "badge " + cls, label);
}

function renderFinding(f) {
  resultEl.replaceChildren();
  const card = el("section", "finding-card");
  card.appendChild(el("span", "draft-label", I18N.draftLabel));
  card.appendChild(el("p", "finding-label", I18N.issueLabel));
  card.appendChild(el("h3", "finding-issue", f.issue_question || "—"));
  if (f.verbatim_passage) {
    card.appendChild(el("p", "finding-label", I18N.verbatimLabel));
    card.appendChild(el("blockquote", "finding-passage", f.verbatim_passage));
    if (f.passage_position) card.appendChild(el("span", "finding-position", f.passage_position));
  }
  card.appendChild(el("p", "finding-label", I18N.evidenceLabel));
  card.appendChild(badge(f.evidence_status));
  if (f.suggested_question) {
    card.appendChild(el("p", "finding-label", I18N.suggestedLabel));
    card.appendChild(el("p", "finding-suggested", f.suggested_question));
  }
  resultEl.appendChild(card);
}

function renderFindings(items) {
  findingsEl.replaceChildren();
  if (!items.length) {
    findingsEl.appendChild(el("li", "finding-empty", I18N.sessionEmpty));
    return;
  }
  for (const f of items) {
    const li = el("li", "finding-item");
    li.appendChild(el("span", "finding-item-issue", f.issue_question || "—"));
    li.appendChild(badge(f.evidence_status));
    findingsEl.appendChild(li);
  }
}

async function loadFindings() {
  if (!sessionId) return;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/findings`);
    const d = await r.json();
    renderFindings(d.findings || []);
  } catch (e) {
    renderFindings([]);
  }
}

function renderTranscript() {
  transcriptList.replaceChildren();
  if (!transcript.length) {
    transcriptList.appendChild(el("li", "transcript-empty", I18N.transcriptEmpty));
    transcriptWrap.hidden = false;
    return;
  }
  for (const seg of transcript) {
    const li = el("li", "transcript-item");
    if (seg.timestamp) li.appendChild(el("span", "transcript-time", new Date(seg.timestamp).toLocaleTimeString()));
    li.appendChild(el("span", "transcript-text", seg.text || ""));
    transcriptList.appendChild(li);
  }
  transcriptWrap.hidden = false;
}

async function loadTranscript() {
  if (!sessionId) return;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/transcript`);
    if (!r.ok) throw new Error();
    const d = await r.json();
    transcript = d.transcript || [];
    renderTranscript();
  } catch (e) {
    audioStatus.textContent = I18N.errTranscript;
  }
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;
  statusEl.textContent = I18N.uploading;
  const form = new FormData();
  form.append("file", file);
  try {
    const r = await fetch(`${API}/api/live/upload`, { method: "POST", body: form });
    if (!r.ok) throw new Error();
    const d = await r.json();
    sessionId = d.session_id;
    transcript = [];
    transcriptList.replaceChildren();
    transcriptWrap.hidden = true;
    consentStatus.textContent = "";
    statusEl.textContent = I18N.docReady;
    loadFindings();
    obsLastIndex = -1;
    lastObservations = [];
    dismissedObsIds.clear();
    observationsList.replaceChildren();
    pollObservations();
  } catch (e) {
    statusEl.textContent = I18N.errUpload;
  }
});

analyzeBtn.addEventListener("click", async () => {
  if (!sessionId) {
    statusEl.textContent = I18N.uploadFirst;
    return;
  }
  const point = pointInput.value.trim();
  if (!point) return;
  analyzeBtn.disabled = true;
  statusEl.textContent = I18N.analyzing;
  try {
    const r = await fetch(`${API}/api/live/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: sessionId, discussion_point: point }),
    });
    if (!r.ok) throw new Error();
    renderFinding(await r.json());
    loadFindings();
    statusEl.textContent = "";
  } catch (e) {
    statusEl.textContent = I18N.errAnalyze;
  } finally {
    analyzeBtn.disabled = false;
  }
});

countrySelect.addEventListener("change", async () => {
  const code = countrySelect.value;
  if (!code) {
    countryInfo.hidden = true;
    return;
  }
  try {
    const r = await fetch(`${API}/api/live/country/${code}`);
    if (!r.ok) throw new Error();
    const d = await r.json();
    const summary = document.documentElement.lang === "de" ? d.summary_de : d.summary_en;
    countryInfo.replaceChildren();
    countryInfo.appendChild(el("p", "country-summary", summary));
    countryInfo.appendChild(el("p", "country-source", `${I18N.sourceLabel}: ${d.source}`));
    countryInfo.appendChild(el("p", "country-disclaimer", I18N.countryDisclaimer));
    countryInfo.hidden = false;
  } catch (e) {
    countryInfo.hidden = true;
  }
});

recordConsentBtn.addEventListener("click", async () => {
  if (!sessionId) {
    consentStatus.textContent = I18N.consentNoSession;
    return;
  }
  const country = countrySelect.value || "unknown";
  const participants = participantsInput.value.split(",").map((s) => s.trim()).filter(Boolean);
  const consent_given = consentCheck.checked;
  try {
    const r = await fetch(`${API}/api/live/consent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, country, participants, consent_given }),
    });
    if (!r.ok) throw new Error();
    consentStatus.textContent = I18N.consentRecorded;
  } catch (e) {
    consentStatus.textContent = I18N.errGeneric;
  }
});

disableAudio.addEventListener("change", () => {
  audioControls.hidden = disableAudio.checked;
});

transcribeBtn.addEventListener("click", async () => {
  const file = audioFileInput.files[0];
  if (!file) {
    audioStatus.textContent = I18N.errTranscribe;
    return;
  }
  if (!sessionId) {
    audioStatus.textContent = I18N.consentNoSession;
    return;
  }
  const mode = document.querySelector('input[name="live-mode"]:checked').value;
  const form = new FormData();
  form.append("file", file);
  const url = mode === "full"
    ? `${API}/api/live/transcribe`
    : `${API}/api/live/session/${sessionId}/dictation`;
  if (mode === "full") form.append("session_id", sessionId);
  transcribeBtn.disabled = true;
  audioStatus.textContent = I18N.transcribing;
  try {
    const r = await fetch(url, { method: "POST", body: form });
    if (r.status === 403) {
      audioStatus.textContent = I18N.errConsent;
      return;
    }
    if (!r.ok) throw new Error();
    audioStatus.textContent = "";
    await loadTranscript();
  } catch (e) {
    audioStatus.textContent = I18N.errTranscribe;
  } finally {
    transcribeBtn.disabled = false;
  }
});

viewTranscriptBtn.addEventListener("click", () => {
  if (!sessionId) {
    audioStatus.textContent = I18N.consentNoSession;
    return;
  }
  loadTranscript();
});

copyToPointBtn.addEventListener("click", () => {
  const text = transcript.map((s) => s.text).filter(Boolean).join("\n");
  pointInput.value = text;
  audioStatus.textContent = I18N.copied;
});

exportBtn.addEventListener("click", () => {
  if (sessionId) window.location.href = `${API}/api/live/session/${sessionId}/export`;
});

deleteBtn.addEventListener("click", async () => {
  if (!sessionId) return;
  if (!window.confirm(I18N.deleteConfirm)) return;
  try {
    await fetch(`${API}/api/live/session/${sessionId}`, { method: "DELETE" });
  } catch (e) {}
  sessionId = null;
  transcript = [];
  fileInput.value = "";
  audioFileInput.value = "";
  resultEl.replaceChildren();
  renderFindings([]);
  transcriptList.replaceChildren();
  transcriptWrap.hidden = true;
  consentStatus.textContent = "";
  audioStatus.textContent = "";
  obsLastIndex = -1;
  lastObservations = [];
  dismissedObsIds.clear();
  observationsList.replaceChildren();
});

// --- Live Meeting (Phase 4a) ---
const meetingRoot = document.querySelector(".live-meeting");
const MEET = meetingRoot ? meetingRoot.dataset : {};
const meetingStart = $("meeting-start"), meetingStop = $("meeting-stop");
const meetingStatus = $("meeting-status"), meetingStatusText = $("meeting-status-text");
const meetingDelay = $("meeting-delay");
const meetingTranscriptWrap = $("meeting-transcript-wrap"), meetingTranscript = $("meeting-transcript");

let mediaRecorder = null;
let mediaStream = null;
let chunkIndex = 0;
let lastSeenIndex = -1;
let pollTimer = null;
let isRecording = false;
let recordingMode = "dictation";

function setMeetingStatus(state, text) {
  meetingStatus.className = "meeting-status status-" + state;
  const labels = { recording: MEET.recording, processing: MEET.processing, idle: MEET.idle };
  meetingStatusText.textContent = text || labels[state] || "";
}

function pickMimeType() {
  if (!window.MediaRecorder) return "";
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];
  for (const t of types) if (MediaRecorder.isTypeSupported(t)) return t;
  return "";
}

async function checkConsent() {
  try {
    const r = await fetch(`${API}/api/live/consent/${sessionId}`);
    if (!r.ok) return false;
    const d = await r.json();
    return (d.consents || []).some((c) => c.consent_given);
  } catch (e) {
    return false;
  }
}

async function uploadChunk(blob, index) {
  const form = new FormData();
  form.append("file", blob, `chunk_${index}.webm`);
  form.append("chunk_index", index);
  form.append("mode", recordingMode);
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/chunk`, { method: "POST", body: form });
    if (r.status === 403) {
      setMeetingStatus("idle", MEET.errConsent);
      await stopRecording();
      return;
    }
    if (!r.ok) {
      setMeetingStatus("idle", MEET.errorChunk);
      return;
    }
    const d = await r.json();
    if (d.status === "backlogged") setMeetingStatus("processing");
    else if (isRecording) setMeetingStatus("recording");
  } catch (e) {
    setMeetingStatus("idle", MEET.errorChunk);
  }
}

async function pollTranscript() {
  if (!sessionId) return;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/transcript/live?since=${lastSeenIndex}`);
    if (!r.ok) return;
    const d = await r.json();
    for (const seg of d.transcript || []) {
      if (seg.chunk_index > lastSeenIndex) lastSeenIndex = seg.chunk_index;
      const text = (seg.text || "").trim();
      if (!text) continue;
      const li = el("li", "transcript-item");
      li.appendChild(el("span", "transcript-time", new Date(seg.timestamp).toLocaleTimeString()));
      li.appendChild(el("span", "transcript-text", text));
      meetingTranscript.appendChild(li);
    }
    meetingTranscriptWrap.hidden = meetingTranscript.children.length === 0;
  } catch (e) {}
}

async function startRecording() {
  if (!sessionId) {
    setMeetingStatus("idle", MEET.noSession);
    return;
  }
  recordingMode = document.querySelector('input[name="meeting-mode"]:checked').value;
  if (recordingMode === "full" && !(await checkConsent())) {
    setMeetingStatus("idle", MEET.errConsent);
    return;
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    setMeetingStatus("idle", MEET.micDenied);
    return;
  }
  const mime = pickMimeType();
  mediaRecorder = mime
    ? new MediaRecorder(mediaStream, { mimeType: mime })
    : new MediaRecorder(mediaStream);
  mediaRecorder.ondataavailable = (ev) => {
    if (ev.data && ev.data.size > 0) uploadChunk(ev.data, chunkIndex++);
  };
  mediaRecorder.start(15000);
  isRecording = true;
  meetingStart.hidden = true;
  meetingStop.hidden = false;
  meetingDelay.hidden = false;
  meetingTranscriptWrap.hidden = meetingTranscript.children.length === 0;
  setMeetingStatus("recording");
  pollTimer = setInterval(pollTranscript, 3000);
  obsPollTimer = setInterval(pollObservations, 10000);
}

async function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (obsPollTimer) { clearInterval(obsPollTimer); obsPollTimer = null; }
  isRecording = false;
  meetingStart.hidden = false;
  meetingStop.hidden = true;
  meetingDelay.hidden = true;
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  setMeetingStatus("processing");
  try {
    if (sessionId) await fetch(`${API}/api/live/session/${sessionId}/stop`, { method: "POST" });
  } catch (e) {}
  mediaRecorder = null;
  await pollTranscript();
  setMeetingStatus("idle");
}

meetingStart.addEventListener("click", startRecording);
meetingStop.addEventListener("click", stopRecording);

// --- Observations (Phase 4b) ---
const observationsList = $("live-observations");
let obsLastIndex = -1;
let obsPollTimer = null;
let lastObservations = [];
const dismissedObsIds = new Set();

function renderObservations(items) {
  observationsList.replaceChildren();
  const visible = items.filter((o) => !o.dismissed && !dismissedObsIds.has(o.obs_id));
  if (!visible.length) {
    observationsList.appendChild(el("li", "observation-empty", I18N.obsEmpty));
    return;
  }
  for (const o of visible) {
    const li = el("li", "observation-item");
    li.appendChild(el("span", "draft-label", I18N.obsAutoLabel));
    li.appendChild(el("p", "observation-issue", o.issue_question || "—"));
    if (o.transcript_excerpt) {
      li.appendChild(el("p", "finding-label", I18N.obsExcerptLabel));
      li.appendChild(el("blockquote", "observation-excerpt", o.transcript_excerpt));
    }
    li.appendChild(el("p", "finding-label", I18N.evidenceLabel));
    li.appendChild(badge(o.evidence_status));
    if (o.suggested_question) {
      li.appendChild(el("p", "finding-label", I18N.suggestedLabel));
      li.appendChild(el("p", "observation-suggested", o.suggested_question));
    }
    const dismissBtn = el("button", "observation-dismiss", I18N.obsDismiss);
    dismissBtn.type = "button";
    dismissBtn.addEventListener("click", () => dismissObservation(o.obs_id));
    li.appendChild(dismissBtn);
    observationsList.appendChild(li);
  }
}

async function pollObservations() {
  if (!sessionId) return;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/observations?since=${obsLastIndex}&document_id=${sessionId}`);
    if (!r.ok) return;
    const d = await r.json();
    if (typeof d.last_index === "number") obsLastIndex = d.last_index;
    lastObservations = d.all || [];
    renderObservations(lastObservations);
  } catch (e) {}
}

async function dismissObservation(obsId) {
  if (!sessionId) return;
  dismissedObsIds.add(obsId);
  renderObservations(lastObservations);
  try {
    await fetch(`${API}/api/live/session/${sessionId}/observations/${obsId}/dismiss`, { method: "POST" });
  } catch (e) {}
}
