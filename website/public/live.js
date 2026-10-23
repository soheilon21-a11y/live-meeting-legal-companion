const root = document.querySelector(".live");
const I18N = root.dataset;
const API = "http://localhost:8002";
const HEALTH_URL = "http://127.0.0.1:8002/health";
let backendUp = null;
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
const diarizeBtn = $("live-diarize"), diarizeSummary = $("live-diarize-summary"), diarizeNote = $("live-diarize-note");
let speakersDetected = 0;
const ttsVoice = $("live-tts-voice"), ttsStatus = $("live-tts-status");
const ttsReadAll = $("live-tts-read-all");
let lastFindings = [];
let currentAudio = null;

async function checkHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2500);
  let up = false;
  try {
    const r = await fetch(HEALTH_URL, { signal: controller.signal });
    up = r.ok;
  } catch (e) {
    up = false;
  } finally {
    clearTimeout(timer);
  }
  applyHealth(up);
  return up;
}

function recheck() {
  return checkHealth();
}

window.recheck = recheck;

async function ensureSession() {
  if (sessionId) return true;
  try {
    const r = await fetch(`${API}/api/live/session`, { method: "POST" });
    if (!r.ok) throw new Error();
    const d = await r.json();
    if (typeof d.session_id !== "string" || !d.session_id.trim()) return false;
    sessionId = d.session_id;
    return true;
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
    return false;
  }
}

async function withDeadSessionRecovery(perform) {
  const first = await perform();
  if (first.status !== 404) return first;
  try {
    const d = await first.clone().json();
    if (d.detail !== "Unknown session") return first;
  } catch (e) {
    return first;
  }
  sessionId = null;
  if (!(await ensureSession())) return first;
  return perform();
}

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
  const speakBtn = el("button", "live-tts-button", I18N.ttsButton);
  speakBtn.type = "button";
  speakBtn.addEventListener("click", () => speakAloud(findingSpeechText(f)));
  card.appendChild(speakBtn);
  resultEl.appendChild(card);
}

function renderFindings(items) {
  lastFindings = items || [];
  findingsEl.replaceChildren();
  if (!lastFindings.length) {
    findingsEl.appendChild(el("li", "finding-empty", I18N.sessionEmpty));
    return;
  }
  for (const f of lastFindings) {
    const li = el("li", "finding-item");
    li.appendChild(el("span", "finding-item-issue", f.issue_question || "—"));
    li.appendChild(badge(f.evidence_status));
    const speakBtn = el("button", "live-tts-button", I18N.ttsButton);
    speakBtn.type = "button";
    speakBtn.addEventListener("click", () => speakAloud(findingSpeechText(f)));
    li.appendChild(speakBtn);
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

function findingSpeechText(f) {
  const parts = [];
  if (f.issue_question) parts.push(f.issue_question);
  if (f.verbatim_passage) parts.push(f.verbatim_passage);
  if (f.suggested_question) parts.push(f.suggested_question);
  return parts.join(". ");
}

function detectLang(text) {
  if (/[äöüßÄÖÜ]/.test(text)) return "de";
  if (/\b(der|die|das|und|ist|nicht|werden|eine|einer|einen|wird|sind|oder|von|mit|zu|den|dem|des|sich|nach|auch|bei|für|auf|als|ein|im|zum|zur|kann|können|müssen|soll|über)\b/i.test(text)) return "de";
  return "en";
}

async function speakAloud(text) {
  const content = (text || "").trim();
  if (!content) {
    ttsStatus.textContent = I18N.ttsEmpty;
    return;
  }
  if (!sessionId) {
    ttsStatus.textContent = I18N.uploadFirst;
    return;
  }
  let lang = ttsVoice.value;
  if (lang === "auto") lang = detectLang(content);
  const spoken = content + " " + I18N.disclaimer;
  ttsStatus.textContent = "";
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: spoken, lang }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      ttsStatus.textContent = d.detail || I18N.ttsError;
      return;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    if (currentAudio) currentAudio.pause();
    currentAudio = new Audio(url);
    await currentAudio.play();
  } catch (e) {
    console.error("speakAloud failed:", e && e.name, "-", e && e.message, e);
    if (e instanceof TypeError) markBackendDown();
    ttsStatus.textContent = I18N.ttsError;
  }
}

function speakerName(i) {
  return I18N.diarizeSpeaker.replace("N", String(i));
}

function speakerSelect(seg) {
  const select = el("select", "speaker-select");
  const count = Math.max(speakersDetected, 1);
  const unknown = el("option", null, I18N.diarizeUnknown);
  unknown.value = "Unknown";
  select.appendChild(unknown);
  for (let i = 1; i <= count; i++) {
    const opt = el("option", null, speakerName(i));
    opt.value = `Speaker ${i}`;
    select.appendChild(opt);
  }
  select.value = seg.speaker || "Unknown";
  select.addEventListener("change", async () => {
    const chosen = select.value;
    await correctSpeaker(seg.chunk_index, chosen);
    seg.speaker = chosen;
  });
  return select;
}

function renderTranscript() {
  transcriptList.replaceChildren();
  diarizeBtn.hidden = !transcript.some((s) => s.chunk_index != null);
  if (!transcript.length) {
    transcriptList.appendChild(el("li", "transcript-empty", I18N.transcriptEmpty));
    transcriptWrap.hidden = false;
    return;
  }
  for (const seg of transcript) {
    const li = el("li", "transcript-item");
    if (seg.timestamp) li.appendChild(el("span", "transcript-time", new Date(seg.timestamp).toLocaleTimeString()));
    if (seg.chunk_index != null) li.appendChild(speakerSelect(seg));
    li.appendChild(el("span", "transcript-text", seg.text || ""));
    transcriptList.appendChild(li);
  }
  transcriptWrap.hidden = false;
}

async function loadTranscript() {
  if (!sessionId) return;
  try {
    const r = await withDeadSessionRecovery(() =>
      fetch(`${API}/api/live/session/${sessionId}/transcript`)
    );
    if (!r.ok) throw new Error();
    const d = await r.json();
    transcript = d.transcript || [];
    renderTranscript();
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
    audioStatus.textContent = I18N.errTranscript;
  }
}

async function correctSpeaker(chunkIndex, speaker) {
  if (!sessionId || chunkIndex == null) return;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/correct-speaker`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chunk_index: chunkIndex, speaker }),
    });
    if (!r.ok) throw new Error();
  } catch (e) {
    audioStatus.textContent = I18N.diarizeError;
  }
}

async function diarize() {
  if (!sessionId) return;
  diarizeBtn.disabled = true;
  try {
    const r = await fetch(`${API}/api/live/session/${sessionId}/diarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!r.ok) throw new Error();
    const d = await r.json();
    speakersDetected = d.speakers_detected || 0;
    transcript = d.transcript || [];
    if (speakersDetected > 0) {
      diarizeSummary.textContent = I18N.diarizeSummary.replace("N", String(speakersDetected));
      diarizeSummary.hidden = false;
      diarizeNote.hidden = false;
    }
    renderTranscript();
  } catch (e) {
    audioStatus.textContent = I18N.diarizeError;
  } finally {
    diarizeBtn.disabled = false;
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
    speakersDetected = 0;
    diarizeSummary.hidden = true;
    diarizeNote.hidden = true;
    diarizeBtn.hidden = true;
    consentStatus.textContent = "";
    statusEl.textContent = I18N.docReady;
    loadFindings();
    obsLastIndex = -1;
    lastObservations = [];
    dismissedObsIds.clear();
    observationsList.replaceChildren();
    pollObservations();
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
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
    if (e instanceof TypeError) markBackendDown();
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
  if (!sessionId && !(await ensureSession())) {
    consentStatus.textContent = I18N.errSessionCreate;
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
    if (e instanceof TypeError) markBackendDown();
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
  const mode = document.querySelector('input[name="live-mode"]:checked').value;
  if (mode === "dictation" && !sessionId && !(await ensureSession())) {
    audioStatus.textContent = I18N.errSessionCreate;
    return;
  }
  if (!sessionId) {
    audioStatus.textContent = I18N.consentNoSession;
    return;
  }
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
    if (e instanceof TypeError) markBackendDown();
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

diarizeBtn.addEventListener("click", diarize);

copyToPointBtn.addEventListener("click", () => {
  const text = transcript.map((s) => s.text).filter(Boolean).join("\n");
  pointInput.value = text;
  audioStatus.textContent = I18N.copied;
});

ttsReadAll.addEventListener("click", () => {
  const text = (lastFindings || []).map(findingSpeechText).filter(Boolean).join(" ");
  speakAloud(text);
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
  speakersDetected = 0;
  diarizeSummary.hidden = true;
  diarizeNote.hidden = true;
  diarizeBtn.hidden = true;
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
    const r = await withDeadSessionRecovery(() =>
      fetch(`${API}/api/live/consent/${sessionId}`)
    );
    if (!r.ok) return false;
    const d = await r.json();
    return (d.consents || []).some((c) => c.consent_given);
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
    return false;
  }
}

async function uploadChunk(blob, index) {
  const form = new FormData();
  form.append("file", blob, `chunk_${index}.webm`);
  form.append("chunk_index", index);
  form.append("mode", recordingMode);
  try {
    const r = await withDeadSessionRecovery(() =>
      fetch(`${API}/api/live/session/${sessionId}/chunk`, { method: "POST", body: form })
    );
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
    if (e instanceof TypeError) markBackendDown();
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
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
  }
}

async function startRecording() {
  if (!sessionId && !(await ensureSession())) {
    setMeetingStatus("idle", I18N.errSessionCreate);
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
  } catch (e) {
    if (e instanceof TypeError) markBackendDown();
  }
}

async function dismissObservation(obsId) {
  if (!sessionId) return;
  dismissedObsIds.add(obsId);
  renderObservations(lastObservations);
  try {
    await fetch(`${API}/api/live/session/${sessionId}/observations/${obsId}/dismiss`, { method: "POST" });
  } catch (e) {}
}

// --- Local app down-state (banner + disabled controls) ---
const backendBanner = $("backend-banner");
const backendRecheck = $("backend-recheck");
const backendLastCheckedTime = $("backend-last-checked-time");

const sessionButtons = [
  meetingStart,
  recordConsentBtn,
  transcribeBtn,
  viewTranscriptBtn,
  analyzeBtn,
  ttsReadAll,
  exportBtn,
];

function setBackendDown(down) {
  backendUp = !down;
  backendBanner.hidden = !down;
  for (const b of sessionButtons) {
    b.disabled = down;
    if (down) {
      b.setAttribute("aria-disabled", "true");
      b.setAttribute("title", I18N.disabledHint);
    } else {
      b.removeAttribute("aria-disabled");
      b.removeAttribute("title");
    }
  }
}

function markBackendDown() {
  setBackendDown(true);
}

function applyHealth(up) {
  backendUp = up;
  backendLastCheckedTime.textContent = new Date().toLocaleTimeString();
  setBackendDown(!up);
}

backendRecheck.addEventListener("click", recheck);

checkHealth();
