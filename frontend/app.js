/* =========================================================================
 * Disability Schemes Assistant — front-end logic (vanilla JS).
 * Talks to the FastAPI backend: /api/chat (SSE), /api/transcribe, /api/tts,
 * /api/upload. Conversations persist in localStorage.
 * ========================================================================= */

const $ = (sel) => document.querySelector(sel);

const els = {
  list: $("#conversation-list"),
  chat: $("#chat"),
  empty: $("#empty-state"),
  suggestions: $("#suggestions"),
  form: $("#composer"),
  input: $("#input"),
  send: $("#send-btn"),
  mic: $("#mic-btn"),
  newChat: $("#new-chat"),
  lang: $("#lang-select"),
  tts: $("#tts-toggle"),
  upload: $("#doc-upload"),
  docStatus: $("#doc-status"),
  status: $("#status-line"),
  sidebar: $("#sidebar"),
  menu: $("#menu-toggle"),
};

const SUGGESTIONS = [
  "What pension is available for 80% locomotor disability?",
  "How do I apply for a UDID card?",
  "Scholarships for a visually impaired college student?",
  "Health insurance schemes for a child with autism?",
];

/* --------------------------------------------------------------- state */
let state = load() || { conversations: {}, currentId: null };
if (!state.currentId || !state.conversations[state.currentId]) newConversation();

function load() {
  try { return JSON.parse(localStorage.getItem("dsa_state")); } catch { return null; }
}
function save() {
  // Audio blobs are not serialisable; strip them before persisting.
  const clone = { currentId: state.currentId, conversations: {} };
  for (const [id, c] of Object.entries(state.conversations)) {
    clone.conversations[id] = {
      title: c.title,
      docText: c.docText || null,
      docName: c.docName || null,
      messages: c.messages.map((m) => ({ role: m.role, content: m.content, sources: m.sources || [] })),
    };
  }
  localStorage.setItem("dsa_state", JSON.stringify(clone));
}
function current() { return state.conversations[state.currentId]; }

function newConversation() {
  const id = Math.random().toString(36).slice(2, 10);
  state.conversations[id] = { title: "New chat", messages: [], docText: null, docName: null };
  state.currentId = id;
  save();
}

/* --------------------------------------------------------------- render */
function renderSidebar() {
  els.list.innerHTML = "";
  for (const [id, c] of Object.entries(state.conversations)) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "conv-item" + (id === state.currentId ? " active" : "");
    btn.type = "button";
    btn.setAttribute("aria-current", id === state.currentId ? "true" : "false");
    btn.innerHTML = `<span class="title">${escapeHtml(c.title)}</span>`;
    btn.onclick = () => { state.currentId = id; save(); renderAll(); };

    const del = document.createElement("button");
    del.className = "del"; del.type = "button";
    del.setAttribute("aria-label", `Delete conversation: ${c.title}`);
    del.textContent = "🗑";
    del.onclick = (e) => { e.stopPropagation(); deleteConversation(id); };

    btn.appendChild(del);
    li.appendChild(btn);
    els.list.appendChild(li);
  }
}

function deleteConversation(id) {
  delete state.conversations[id];
  if (state.currentId === id) {
    const ids = Object.keys(state.conversations);
    if (ids.length) state.currentId = ids[0]; else newConversation();
  }
  save(); renderAll();
}

function renderChat() {
  const c = current();
  els.chat.querySelectorAll(".msg-row").forEach((n) => n.remove());
  els.empty.style.display = c.messages.length ? "none" : "block";
  for (const m of c.messages) addBubble(m.role, m.content, m.sources, m.audio);
  els.chat.scrollTop = els.chat.scrollHeight;
}

function renderAll() { renderSidebar(); renderChat(); }

function addBubble(role, markdown, sources, audioUrl) {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  const avatar = role === "user" ? "🧑" : "♿";

  const body = document.createElement("div");
  body.className = "bubble";
  body.innerHTML = role === "assistant" ? renderMarkdown(markdown) : `<p>${escapeHtml(markdown)}</p>`;

  if (sources && sources.length) {
    const s = document.createElement("div");
    s.className = "sources";
    s.innerHTML = "<strong style='font-size:.72rem'>Sources:</strong> " +
      sources.map((x) => `<span class="source-tag">${escapeHtml(x)}</span>`).join("");
    body.appendChild(s);
  }
  if (audioUrl) {
    const a = document.createElement("audio");
    a.className = "msg-audio"; a.controls = true; a.src = audioUrl;
    body.appendChild(a);
  }

  row.innerHTML = `<div class="avatar" aria-hidden="true">${avatar}</div>`;
  row.appendChild(body);
  els.chat.appendChild(row);
  els.chat.scrollTop = els.chat.scrollHeight;
  return body;
}

function renderMarkdown(md) {
  const html = window.marked ? window.marked.parse(md) : `<p>${escapeHtml(md)}</p>`;
  return html;
}
function highlight(scope) {
  if (window.hljs) scope.querySelectorAll("pre code").forEach((b) => window.hljs.highlightElement(b));
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function setStatus(msg, isError = false) {
  els.status.textContent = msg;
  els.status.classList.toggle("error", isError);
}

/* --------------------------------------------------------------- send flow */
els.form.addEventListener("submit", (e) => { e.preventDefault(); send(); });
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
els.input.addEventListener("input", () => {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 180) + "px";
});

async function send(forcedText, forcedLang) {
  const text = (forcedText ?? els.input.value).trim();
  if (!text || els.send.disabled) return;

  const c = current();
  c.messages.push({ role: "user", content: text });
  if (c.title === "New chat") c.title = text.slice(0, 42) + (text.length > 42 ? "…" : "");
  els.input.value = ""; els.input.style.height = "auto";
  addBubble("user", text);
  renderSidebar(); save();

  els.send.disabled = true;
  const assistantBody = addBubble("assistant", "");
  assistantBody.innerHTML = `<div class="typing" aria-label="Assistant is typing"><span></span><span></span><span></span></div>`;
  setStatus("Thinking…");

  const payload = {
    message: text,
    history: c.messages.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
    lang: forcedLang || els.lang.value,
    doc_text: c.docText || null,
  };

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    let streamed = "";
    let final = null;
    await readSSE(res.body, (evt) => {
      if (evt.type === "token") {
        streamed += evt.text;
        assistantBody.innerHTML = renderMarkdown(streamed);
        els.chat.scrollTop = els.chat.scrollHeight;
      } else if (evt.type === "final") {
        final = evt;
      } else if (evt.type === "error") {
        throw new Error(evt.message);
      }
    });

    const answer = final ? final.answer : streamed;
    const sources = final ? final.sources : [];
    assistantBody.innerHTML = renderMarkdown(answer);
    highlight(assistantBody);
    if (sources.length) {
      const s = document.createElement("div");
      s.className = "sources";
      s.innerHTML = "<strong style='font-size:.72rem'>Sources:</strong> " +
        sources.map((x) => `<span class="source-tag">${escapeHtml(x)}</span>`).join("");
      assistantBody.appendChild(s);
    }

    const msg = { role: "assistant", content: answer, sources };
    c.messages.push(msg);
    save();
    setStatus("");

    // Text-to-speech in the user's language.
    if (els.tts.checked && final) {
      if (final.tts_available) await speak(answer, final.lang, assistantBody, msg);
      else setStatus("🔇 Voice output isn't available for this language yet.");
    }
  } catch (err) {
    assistantBody.innerHTML =
      `<p><strong>Couldn't get an answer.</strong> ${escapeHtml(err.message)}</p>` +
      `<p class="hint">If this says “Access denied / network settings”, disconnect any VPN — Groq blocks VPN IPs.</p>`;
    setStatus("Request failed.", true);
  } finally {
    els.send.disabled = false;
    els.input.focus();
  }
}

/* Parse a Server-Sent Events stream from a fetch body. */
async function readSSE(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop();
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (line) onEvent(JSON.parse(line.slice(5).trim()));
    }
  }
}

/* --------------------------------------------------------------- TTS */
async function speak(text, lang, bodyEl, msg) {
  try {
    setStatus("🔈 Preparing audio…");
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: stripMarkdown(text), lang }),
    });
    if (res.status === 204) { setStatus(""); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = document.createElement("audio");
    audio.className = "msg-audio"; audio.controls = true; audio.src = url;
    bodyEl.appendChild(audio);
    msg.audio = url;
    audio.play().catch(() => {}); // autoplay may need a gesture; controls remain
    setStatus("");
  } catch { setStatus(""); }
}
function stripMarkdown(t) {
  return t.replace(/```[\s\S]*?```/g, " code example omitted. ")
          .replace(/[*_#>`~\[\]]+/g, " ").replace(/\s{2,}/g, " ").trim();
}

/* --------------------------------------------------------------- voice input */
let mediaRecorder = null, chunks = [];
els.mic.addEventListener("click", toggleMic);

async function toggleMic() {
  if (mediaRecorder && mediaRecorder.state === "recording") { mediaRecorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia) { setStatus("Microphone not supported in this browser.", true); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    mediaRecorder.onstop = () => { stream.getTracks().forEach((t) => t.stop()); transcribe(); };
    mediaRecorder.start();
    els.mic.setAttribute("aria-pressed", "true");
    setStatus("🎙️ Listening… tap the mic again to stop.");
  } catch {
    setStatus("Microphone permission denied.", true);
  }
}

async function transcribe() {
  els.mic.setAttribute("aria-pressed", "false");
  setStatus("🎧 Transcribing (detecting language)…");
  const blob = new Blob(chunks, { type: "audio/webm" });
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");
  try {
    const res = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await res.json();
    if (data.text) { setStatus(""); send(data.text, data.lang || "auto"); }
    else setStatus("Couldn't hear that clearly — please try again.", true);
  } catch (err) {
    setStatus("Transcription failed: " + err.message, true);
  }
}

/* --------------------------------------------------------------- upload */
els.upload.addEventListener("change", async () => {
  const file = els.upload.files[0];
  if (!file) return;
  els.docStatus.textContent = "Reading document…";
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.text) {
      current().docText = data.text; current().docName = data.name; save();
      els.docStatus.textContent = `Using “${data.name}” (${data.chars} chars) in this chat.`;
    } else {
      els.docStatus.textContent = "Could not read that file.";
    }
  } catch { els.docStatus.textContent = "Upload failed."; }
});

/* --------------------------------------------------------------- misc UI */
els.newChat.addEventListener("click", () => { newConversation(); renderAll(); els.input.focus(); });
els.menu.addEventListener("click", () => {
  const open = els.sidebar.classList.toggle("open");
  els.menu.setAttribute("aria-expanded", String(open));
});

function buildSuggestions() {
  els.suggestions.innerHTML = "";
  for (const s of SUGGESTIONS) {
    const b = document.createElement("button");
    b.className = "suggestion"; b.type = "button"; b.textContent = s;
    b.onclick = () => send(s);
    els.suggestions.appendChild(b);
  }
}

async function loadLanguages() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    for (const [name, code] of Object.entries(data.languages || {})) {
      const opt = document.createElement("option");
      opt.value = code; opt.textContent = name;
      els.lang.appendChild(opt);
    }
  } catch { /* keep just Auto-detect */ }
}

/* --------------------------------------------------------------- init */
window.addEventListener("DOMContentLoaded", async () => {
  if (window.marked) window.marked.setOptions({ breaks: true });
  buildSuggestions();
  renderAll();
  await loadLanguages();
  const c = current();
  if (c.docName) els.docStatus.textContent = `Using “${c.docName}” in this chat.`;
  els.input.focus();
});
