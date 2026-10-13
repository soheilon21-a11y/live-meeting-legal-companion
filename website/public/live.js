const root = document.querySelector(".live");
const I18N = root.dataset;
const API = "http://localhost:8002";
let sessionId = null;
const $ = (id) => document.getElementById(id);
const fileInput = $("live-file"), pointInput = $("live-point"), analyzeBtn = $("live-analyze");
const statusEl = $("live-status"), resultEl = $("live-result"), findingsEl = $("live-findings");
const exportBtn = $("live-export"), deleteBtn = $("live-delete");

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
    statusEl.textContent = I18N.docReady;
    loadFindings();
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
  fileInput.value = "";
  resultEl.replaceChildren();
  renderFindings([]);
});
