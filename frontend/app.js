/* =========================================================================
 * Sneh Saathi (स्नेह साथी) — front-end logic (vanilla JS).
 * Interface text comes from i18n.js via t(); answers come in the user's language.
 * Talks to the FastAPI backend: /api/chat (SSE), /api/followups,
 * /api/insights, /api/transcribe, /api/tts, /api/upload.
 * Conversations persist in localStorage.
 * ========================================================================= */

const $ = (sel) => document.querySelector(sel);

const els = {
  list: $("#conversation-list"),
  chat: $("#chat"),
  empty: $("#empty-state"),
  suggestions: $("#suggestions"),
  topics: $("#topics"),
  langChips: $("#lang-chips"),
  form: $("#composer"),
  input: $("#input"),
  send: $("#send-btn"),
  mic: $("#mic-btn"),
  homeMic: $("#home-mic"),
  newChat: $("#new-chat"),
  newChatTop: $("#new-chat-top"),
  lang: $("#lang-select"),
  tts: $("#tts-toggle"),
  textSize: $("#text-size"),
  contrast: $("#contrast-toggle"),
  upload: $("#doc-upload"),
  docChip: $("#doc-chip"),
  docName: $("#doc-name"),
  docRemove: $("#doc-remove"),
  status: $("#status-line"),
  sidebar: $("#sidebar"),
  menu: $("#menu-toggle"),
  sidebarClose: $("#sidebar-close"),
  panel: $("#insights"),
  panelToggle: $("#panel-toggle"),
  panelClose: $("#panel-close"),
  badge: $("#match-badge"),
  profile: $("#profile-chips"),
  profileEmpty: $("#profile-empty"),
  schemes: $("#scheme-list"),
  schemesEmpty: $("#schemes-empty"),
  schemesLoading: $("#schemes-loading"),
  sourcesSec: $("#sources-sec"),
  sources: $("#source-list"),
  scrim: $("#scrim"),
};

// Native names, so people can find their own language at a glance.
const NATIVE = {
  en: "English", hi: "हिन्दी", ta: "தமிழ்", te: "తెలుగు", mr: "मराठी", bn: "বাংলা",
  gu: "ગુજરાતી", kn: "ಕನ್ನಡ", ml: "മലയാളം", pa: "ਪੰਜਾਬੀ", or: "ଓଡ଼ିଆ", as: "অসমীয়া", ur: "اردو",
};
const HOME_LANGS = ["auto", "en", "hi", "ta", "bn", "mr", "te"];
const TEXT_SIZES = [["", "sizeNormal"], ["lg", "sizeLarge"], ["xl", "sizeXl"]];
const STATUS = {
  eligible: { icon: "circle-check", label: "eligible" },
  check: { icon: "alert-circle", label: "checkDetails" },
  not_eligible: { icon: "circle-x", label: "notEligible" },
};

/* --------------------------------------------------------------- helpers */
function icon(name, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="/icons.svg#i-${name}"/></svg>`;
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeUrl(u) {
  return /^https?:\/\//i.test(u || "") ? u : "";
}
function hostOf(u) {
  try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; }
}
function setStatus(msg, isError = false) {
  els.status.textContent = msg;
  els.status.classList.toggle("error", isError);
}
function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch { return null; }
}
const scrollDown = () => { els.chat.scrollTop = els.chat.scrollHeight; };

/* --------------------------------------------------------------- state */
let state = load() || { conversations: {}, currentId: null };
if (!state.currentId || !state.conversations[state.currentId]) newConversation();

function load() {
  try { return JSON.parse(localStorage.getItem("dsa_state")); } catch { return null; }
}
function save() {
  // Audio blob URLs are not serialisable; everything else round-trips.
  const clone = { currentId: state.currentId, conversations: {} };
  for (const [id, c] of Object.entries(state.conversations)) {
    clone.conversations[id] = {
      title: c.title,
      docText: c.docText || null,
      docName: c.docName || null,
      insights: c.insights || null,
      messages: c.messages.map((m) => ({
        role: m.role, content: m.content, sources: m.sources || [],
        sourceLinks: m.sourceLinks || [], lang: m.lang || null, followups: m.followups || null,
      })),
    };
  }
  try { localStorage.setItem("dsa_state", JSON.stringify(clone)); } catch { /* storage full or blocked */ }
}
function current() { return state.conversations[state.currentId]; }

function newConversation() {
  const id = Math.random().toString(36).slice(2, 10);
  state.conversations[id] = { title: "New chat", messages: [], docText: null, docName: null, insights: null };
  state.currentId = id;
  save();
}

/* --------------------------------------------------------------- render: history */
function renderSidebar() {
  els.list.innerHTML = "";
  const ids = Object.keys(state.conversations).reverse(); // newest first
  for (const id of ids) {
    const c = state.conversations[id];
    const li = document.createElement("li");
    li.className = "conv" + (id === state.currentId ? " active" : "");

    const open = document.createElement("button");
    open.type = "button";
    open.className = "conv-open";
    open.textContent = c.title === "New chat" ? t("newChat") : c.title;  // "New chat" is the untitled marker
    if (id === state.currentId) open.setAttribute("aria-current", "page");
    open.onclick = () => { state.currentId = id; save(); renderAll(); closeDrawers(); };

    const del = document.createElement("button");
    del.type = "button";
    del.className = "icon-btn";
    del.setAttribute("aria-label", t("deleteChat", { title: c.title === "New chat" ? t("newChat") : c.title }));
    del.innerHTML = icon("trash");
    del.onclick = () => deleteConversation(id);

    li.append(open, del);
    els.list.appendChild(li);
  }
}

function deleteConversation(id) {
  delete state.conversations[id];
  if (state.currentId === id) {
    const ids = Object.keys(state.conversations);
    if (ids.length) state.currentId = ids[ids.length - 1]; else newConversation();
  }
  save(); renderAll();
}

/* --------------------------------------------------------------- render: chat */
function renderChat() {
  stopAudio();
  const c = current();
  els.chat.querySelectorAll(".msg-row").forEach((n) => n.remove());
  els.empty.hidden = c.messages.length > 0;
  c.messages.forEach((m, i) => {
    const isLast = i === c.messages.length - 1;
    if (m.role === "user") addUserRow(m.content);
    else {
      const row = addAssistantRow();
      fillAssistant(row, m, { followups: isLast ? m.followups : null });
      if (isLast && c.insights) {
        addMatchesPill(row, (c.insights.schemes || []).filter((s) => s.status !== "not_eligible").length);
      }
    }
  });
  renderDoc();
  if (c.messages.length) scrollDown(); else els.chat.scrollTop = 0;
}

function renderAll() { renderSidebar(); renderChat(); renderInsights(); }

function addUserRow(text) {
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `<div class="bubble" dir="auto"><p>${escapeHtml(text)}</p></div>`;
  els.chat.appendChild(row);
  scrollDown();
  return row;
}

function addAssistantRow() {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.innerHTML = `<div class="avatar" aria-hidden="true">${icon("accessible")}</div>
    <div class="msg-main"><div class="bubble" dir="auto"></div></div>`;
  els.chat.appendChild(row);
  scrollDown();
  return row;
}

/* Answer text plus everything under it: sources, Listen/Copy, follow-ups. */
function fillAssistant(row, msg, { followups } = {}) {
  const main = row.querySelector(".msg-main");
  const bubble = row.querySelector(".bubble");
  bubble.innerHTML = renderMarkdown(msg.content);
  highlight(bubble);
  main.querySelectorAll(":scope > :not(.bubble)").forEach((n) => n.remove());

  const links = msg.sourceLinks && msg.sourceLinks.length
    ? msg.sourceLinks
    : (msg.sources || []).map((s) => ({ name: s, url: "" }));
  if (links.length) {
    const s = document.createElement("div");
    s.className = "msg-sources";
    s.setAttribute("aria-label", t("sources"));
    s.innerHTML = links.slice(0, 4).map(sourceTag).join("");
    main.appendChild(s);
  }

  const actions = document.createElement("div");
  actions.className = "msg-actions";
  const listen = document.createElement("button");
  listen.type = "button";
  listen.className = "act-btn listen";
  listen.setAttribute("aria-pressed", "false");
  listen.innerHTML = `${icon("volume")}<span data-i18n="listen">${t("listen")}</span>`;
  listen.onclick = () => toggleListen(listen, msg);

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "act-btn";
  copy.innerHTML = `${icon("copy")}<span data-i18n="copy">${t("copy")}</span>`;
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(msg.content);
      copy.querySelector("span").textContent = t("copied");
      setTimeout(() => { copy.querySelector("span").textContent = t("copy"); }, 1600);
    } catch { setStatus(t("copyFailed"), true); }
  };
  actions.append(listen, copy);
  if (msg.lang && msg.lang !== "en" && NATIVE[msg.lang]) {
    const tag = document.createElement("span");
    tag.className = "lang-tag";
    tag.textContent = NATIVE[msg.lang];
    actions.appendChild(tag);
  }
  main.appendChild(actions);

  if (followups && followups.length) main.appendChild(buildChips(followups));
  return listen;
}

function sourceTag(l) {
  const url = safeUrl(l.url);
  const label = escapeHtml(l.name);
  return url
    ? `<a class="source-tag" href="${escapeHtml(url)}" target="_blank" rel="noopener" title="${escapeHtml(url)}">${icon("link")}${label}</a>`
    : `<span class="source-tag">${icon("file-text")}${label}</span>`;
}

/* On phones and tablets the panel is hidden, so point to it from the chat. */
function addMatchesPill(row, count) {
  row.querySelector(".matches-pill")?.remove();
  if (!count) return;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "matches-pill";
  b.dataset.count = count;  // kept so the label can be re-translated
  b.innerHTML = `${icon("list-details")}<span>${pillText(count)}</span>`;
  b.onclick = () => openPanel(b);
  const actions = row.querySelector(".msg-actions");
  actions.after(b);
}

function pillText(count) {
  return count > 1 ? t("seeMatches", { n: count }) : t("seeMatch");
}

/* Clickable follow-up question chips shown under the latest answer. */
function buildChips(items) {
  const wrap = document.createElement("div");
  wrap.className = "followups";
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", t("followupsAria"));
  items.forEach((q, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.dir = "auto";
    b.style.animationDelay = `${i * 60}ms`;
    b.innerHTML = `${icon("sparkles")}<span>${escapeHtml(q)}</span>`;
    b.onclick = () => send(q);
    wrap.appendChild(b);
  });
  return wrap;
}

function renderMarkdown(md) {
  return window.marked ? window.marked.parse(md || "") : `<p>${escapeHtml(md)}</p>`;
}
function highlight(scope) {
  if (window.hljs) scope.querySelectorAll("pre code").forEach((b) => window.hljs.highlightElement(b));
  scope.querySelectorAll("a[href^='http']").forEach((a) => { a.target = "_blank"; a.rel = "noopener"; });
}

/* --------------------------------------------------------------- render: matches panel */
let insightsLoading = false;

function renderInsights(loading = insightsLoading) {
  const ins = current().insights || { profile: [], schemes: [], sources: [] };

  els.profile.innerHTML = (ins.profile || []).map((p) =>
    `<li><span class="k">${escapeHtml(p.label)}</span><span class="v" dir="auto">${escapeHtml(p.value)}</span></li>`
  ).join("");
  els.profileEmpty.hidden = (ins.profile || []).length > 0;

  els.schemesLoading.hidden = !loading;
  els.schemes.setAttribute("aria-busy", String(loading));
  const schemes = loading ? [] : ins.schemes || [];
  els.schemes.innerHTML = "";
  for (const s of schemes) els.schemes.appendChild(schemeCard(s));
  els.schemesEmpty.hidden = loading || schemes.length > 0;

  const eligible = (ins.schemes || []).filter((s) => s.status !== "not_eligible").length;
  els.badge.hidden = !eligible;
  els.badge.textContent = eligible;
  els.panelToggle.setAttribute("aria-label", eligible ? t("matchesCount", { n: eligible }) : t("matches"));

  // Several scheme files share a portal; list each site once.
  const seen = new Set();
  const srcs = (ins.sources || []).filter((l) => {
    const key = hostOf(safeUrl(l.url)) || l.name;
    return !seen.has(key) && seen.add(key);
  }).slice(0, 6);
  els.sourcesSec.hidden = !srcs.length;
  els.sources.innerHTML = srcs.map((l) => {
    const url = safeUrl(l.url);
    return url
      ? `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener" title="${escapeHtml(l.name)}">${icon("link")}${escapeHtml(hostOf(url) || l.name)}</a></li>`
      : `<li><span>${icon("file-text")}${escapeHtml(l.name)}</span></li>`;
  }).join("");
}

function schemeCard(s) {
  const st = STATUS[s.status] || STATUS.check;
  const url = safeUrl(s.url);
  const li = document.createElement("li");
  li.className = `scheme ${s.status}`;
  li.innerHTML = `
    ${url
      ? `<a class="scheme-name" href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(s.name)}${icon("external-link")}<span class="sr-only"> ${t("opensOfficial")}</span></a>`
      : `<span class="scheme-name">${escapeHtml(s.name)}</span>`}
    ${s.benefit ? `<div class="scheme-benefit" dir="auto">${escapeHtml(s.benefit)}</div>` : ""}
    ${s.reason ? `<div class="scheme-reason" dir="auto">${escapeHtml(s.reason)}</div>` : ""}
    <div class="scheme-foot">
      <span class="status ${s.status}">${icon(st.icon)}${t(st.label)}</span>
    </div>`;
  const ask = document.createElement("button");
  ask.type = "button";
  ask.className = "link-btn";
  ask.textContent = t("askAboutThis");
  ask.setAttribute("aria-label", t("askAboutAria", { name: s.name }));
  ask.onclick = () => { closeDrawers(); send(t("askAboutQ", { name: s.name })); };
  li.querySelector(".scheme-foot").appendChild(ask);
  return li;
}

/* Fetch profile + matched schemes for the latest turn (non-blocking). */
async function loadInsights(row, finalEvt, historyBefore, conv) {
  const isCurrent = () => conv === current();
  insightsLoading = true;
  if (isCurrent()) renderInsights(true);
  try {
    const res = await fetch("/api/insights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: finalEvt.english_question || "",
        history: historyBefore,
        lang: finalEvt.lang || "en",
      }),
    });
    const data = await res.json();
    const prev = conv.insights || {};
    // An empty result means "nothing new", so keep what we already knew.
    conv.insights = {
      profile: data.profile && data.profile.length ? data.profile : prev.profile || [],
      schemes: data.schemes && data.schemes.length ? data.schemes : prev.schemes || [],
      sources: finalEvt.source_links || prev.sources || [],
    };
    save();
    const n = (data.schemes || []).filter((s) => s.status !== "not_eligible").length;
    if (row.isConnected) addMatchesPill(row, n);
  } catch { /* the panel is optional; keep its previous state */ }
  insightsLoading = false;
  if (isCurrent()) renderInsights(false);
}

/* --------------------------------------------------------------- send flow */
els.form.addEventListener("submit", (e) => { e.preventDefault(); send(); });
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
});
els.input.addEventListener("input", autoGrow);
function autoGrow() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(els.input.scrollHeight, 180) + "px";
  els.input.style.overflowY = els.input.scrollHeight > 180 ? "auto" : "hidden";
}

let busy = false;

/* A failure with a message that is safe and useful to show the user. */
class ChatError extends Error {
  constructor(message, code) { super(message); this.code = code; }
}

// Failures the server can't report because the request never got an answer.
function toChatError(err) {
  if (err instanceof ChatError) return err;
  if (!navigator.onLine) return new ChatError(t("err_offline"), "offline");
  if (err instanceof TypeError) return new ChatError(t("err_network"), "network"); // fetch() could not connect
  return new ChatError(t("err_server"), "client");
}

// The server's messages are English; show our own wording when we have one.
function errorText(err) {
  const key = `err_${err.code}`;
  return key in STRINGS.en ? t(key) : err.message;
}

/* Replace the assistant bubble with a readable error and a Try again button. */
function showError(row, err, onRetry) {
  row.classList.add("error");
  const main = row.querySelector(".msg-main");
  main.querySelectorAll(":scope > :not(.bubble)").forEach((n) => n.remove());
  const bubble = row.querySelector(".bubble");
  bubble.setAttribute("role", "alert");
  bubble.innerHTML = `<p class="err-title">${icon("alert-circle")}<span data-i18n="noAnswer">${t("noAnswer")}</span></p>
    <p>${escapeHtml(errorText(err))}</p>`;

  const actions = document.createElement("div");
  actions.className = "msg-actions";
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "act-btn";
  retry.innerHTML = `${icon("refresh")}<span data-i18n="tryAgain">${t("tryAgain")}</span>`;
  retry.onclick = onRetry;
  actions.appendChild(retry);
  if (err.code) {
    const code = document.createElement("span");
    code.className = "err-code";
    code.textContent = t("errorCode", { code: err.code });
    actions.appendChild(code);
  }
  main.appendChild(actions);
  scrollDown();
}

async function send(forcedText, forcedLang) {
  const text = (forcedText ?? els.input.value).trim();
  if (!text || busy) return;
  busy = true;
  els.send.disabled = true;
  stopAudio();

  const c = current();
  // Chips and the matches pill belong to the previous turn only.
  els.chat.querySelectorAll(".followups, .matches-pill").forEach((n) => n.remove());
  c.messages.forEach((m) => { m.followups = null; });

  const historyBefore = c.messages.map((m) => ({ role: m.role, content: m.content }));
  const userMsg = { role: "user", content: text };
  c.messages.push(userMsg);
  if (c.title === "New chat") c.title = text.slice(0, 48) + (text.length > 48 ? "…" : "");
  els.input.value = ""; autoGrow();
  els.empty.hidden = true;
  const userRow = addUserRow(text);
  renderSidebar(); save();

  const row = addAssistantRow();
  const bubble = row.querySelector(".bubble");
  bubble.innerHTML = `<div class="typing" role="status" aria-label="${t("typing")}"><span></span><span></span><span></span></div>`;
  setStatus(t("thinking"));

  const payload = {
    message: text,
    history: historyBefore,
    lang: forcedLang || els.lang.value,
    doc_text: c.docText || null,
  };

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) throw new ChatError(t("err_server"), `http_${res.status}`);

    let streamed = "";
    let final = null;
    await readSSE(res.body, (evt) => {
      if (evt.type === "token") {
        streamed += evt.text;
        bubble.innerHTML = renderMarkdown(streamed);
        scrollDown();
      } else if (evt.type === "final") {
        final = evt;
      } else if (evt.type === "error") {
        throw new ChatError(evt.message, evt.code);
      }
    });

    const msg = {
      role: "assistant",
      content: final ? final.answer : streamed,
      sources: final ? final.sources : [],
      sourceLinks: final ? final.source_links || [] : [],
      lang: final ? final.lang : null,
    };
    c.messages.push(msg);
    const listenBtn = fillAssistant(row, msg);
    save();
    setStatus("");
    scrollDown();

    // On Auto, follow the language people actually write in: a Hindi question
    // switches the interface to Hindi (and an English one back).
    if (final && els.lang.value === "auto" && ["hi", "en"].includes(final.lang) && final.lang !== UI_LANG) {
      pref("dsa_ui", final.lang);
      applyUiLanguage();
    }

    if (final) {
      // Follow-up chips and the matches panel load in parallel, after the answer.
      loadFollowups(row, final, historyBefore, msg);
      if (msg.sources.length) loadInsights(row, final, historyBefore, c);

      if (isSpeakOn()) {
        if (final.tts_available) toggleListen(listenBtn, msg);
        else setStatus(t("noVoice"));
      }
    }
  } catch (err) {
    console.error(err);
    setStatus("");
    showError(row, toChatError(err), () => {
      // Drop the failed turn, then ask the same question again.
      if (current() !== c) return;
      const i = c.messages.lastIndexOf(userMsg);
      if (i !== -1) c.messages.splice(i, 1);
      userRow.remove(); row.remove(); save();
      send(text, forcedLang);
    });
  } finally {
    busy = false;
    els.send.disabled = false;
    if (!isPhone()) els.input.focus();
  }
}

async function loadFollowups(row, finalEvt, historyBefore, msg) {
  try {
    const res = await fetch("/api/followups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: finalEvt.english_question || "",
        answer: finalEvt.answer || "",
        history: historyBefore,
        lang: finalEvt.lang || "en",
      }),
    });
    const data = await res.json();
    if (data.followups && data.followups.length && row.isConnected && !busy) {
      msg.followups = data.followups;
      save();
      row.querySelector(".msg-main").appendChild(buildChips(data.followups));
      scrollDown();
    }
  } catch { /* chips are optional; ignore failures */ }
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

/* --------------------------------------------------------------- listen (TTS) */
const player = new Audio();
let playingBtn = null;

function setListenState(btn, playing) {
  if (!btn) return;
  btn.setAttribute("aria-pressed", String(playing));
  btn.innerHTML = playing
    ? `${icon("player-stop")}<span data-i18n="stop">${t("stop")}</span>`
    : `${icon("volume")}<span data-i18n="listen">${t("listen")}</span>`;
}
function stopAudio() {
  player.pause();
  setListenState(playingBtn, false);
  playingBtn = null;
}
player.addEventListener("ended", () => { setListenState(playingBtn, false); playingBtn = null; });

async function toggleListen(btn, msg) {
  if (playingBtn === btn) { stopAudio(); return; }
  stopAudio();
  if (!msg.audio) {
    btn.setAttribute("aria-busy", "true");
    setStatus(t("preparingAudio"));
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Sent raw: the server strips Markdown/emoji and adds natural pauses.
        body: JSON.stringify({ text: msg.content, lang: msg.lang || "en" }),
      });
      if (res.status === 204) { setStatus(t("noVoice")); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      msg.audio = URL.createObjectURL(await res.blob());
      setStatus("");
    } catch {
      setStatus(t("audioFailed"), true);
      return;
    } finally {
      btn.removeAttribute("aria-busy");
    }
  }
  player.src = msg.audio;
  playingBtn = btn;
  setListenState(btn, true);
  // Autoplay can be blocked without a recent tap; the Listen button still works.
  player.play().catch(() => { setListenState(btn, false); playingBtn = null; });
}

function isSpeakOn() { return els.tts.getAttribute("aria-pressed") === "true"; }
els.tts.addEventListener("click", () => {
  const on = !isSpeakOn();
  els.tts.setAttribute("aria-pressed", String(on));
  els.tts.querySelector("use").setAttribute("href", `/icons.svg#i-${on ? "volume" : "volume-off"}`);
  pref("dsa_tts", on ? "1" : "0");
  if (!on) stopAudio();
});

/* --------------------------------------------------------------- voice input */
let mediaRecorder = null, chunks = [];
els.mic.addEventListener("click", toggleMic);
els.homeMic.addEventListener("click", toggleMic);

function setMicState(on) {
  for (const b of [els.mic, els.homeMic]) {
    b.setAttribute("aria-pressed", String(on));
    b.setAttribute("aria-label", on ? t("stopRecording") : t("askByVoice"));
    b.querySelector("use").setAttribute("href", `/icons.svg#i-${on ? "player-stop" : "microphone"}`);
  }
  document.querySelector(".big-mic-label").textContent = on ? t("listeningTap") : t("tapAndSpeak");
}
const isRecording = () => !!mediaRecorder && mediaRecorder.state === "recording";

async function toggleMic() {
  if (mediaRecorder && mediaRecorder.state === "recording") { mediaRecorder.stop(); return; }
  if (!navigator.mediaDevices?.getUserMedia) { setStatus(t("micUnsupported"), true); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stopAudio();
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    mediaRecorder.onstop = () => { stream.getTracks().forEach((t) => t.stop()); transcribe(); };
    mediaRecorder.start();
    setMicState(true);
    setStatus(t("listening"));
  } catch {
    setStatus(t("micDenied"), true);
  }
}

async function transcribe() {
  setMicState(false);
  setStatus(t("transcribing"));
  const blob = new Blob(chunks, { type: "audio/webm" });
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");
  try {
    const res = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await res.json();
    if (data.text) { setStatus(""); send(data.text, data.lang || "auto"); }
    else setStatus(data.error ? (UI_LANG === "en" ? data.error : t("notHeard")) : t("notHeard"), true);
  } catch {
    setStatus(t("transcribeFailed"), true);
  }
}

/* --------------------------------------------------------------- document upload */
els.upload.addEventListener("change", async () => {
  const file = els.upload.files[0];
  if (!file) return;
  setStatus(t("reading", { name: file.name }));
  const fd = new FormData(); fd.append("file", file);
  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.text) {
      current().docText = data.text; current().docName = data.name; save();
      renderDoc();
      setStatus(t("askAboutDoc", { name: data.name }));
    } else {
      setStatus(data.error && UI_LANG === "en" ? data.error : t("unreadable"), true);
    }
  } catch { setStatus(t("uploadFailed"), true); }
  els.upload.value = "";
});
els.docRemove.addEventListener("click", () => {
  current().docText = null; current().docName = null; save();
  renderDoc(); els.input.focus();
});
function renderDoc() {
  const name = current().docName;
  els.docChip.hidden = !name;
  els.docName.textContent = name ? t("usingDoc", { name }) : "";
}

/* --------------------------------------------------------------- drawers + sheet */
let lastOpener = null;

function openDrawer(el, opener) {
  closeDrawers(false);
  lastOpener = opener || document.activeElement;
  el.classList.add("open");
  els.scrim.hidden = false;
  if (el === els.sidebar) els.menu.setAttribute("aria-expanded", "true");
  if (el === els.panel) els.panelToggle.setAttribute("aria-expanded", "true");
  el.querySelector("button, select, a")?.focus();
}
function closeDrawers(restoreFocus = true) {
  const wasOpen = els.sidebar.classList.contains("open") || els.panel.classList.contains("open");
  els.sidebar.classList.remove("open");
  els.panel.classList.remove("open");
  els.scrim.hidden = true;
  els.menu.setAttribute("aria-expanded", "false");
  els.panelToggle.setAttribute("aria-expanded", "false");
  if (wasOpen && restoreFocus && lastOpener?.isConnected) lastOpener.focus();
}
function openPanel(opener) {
  // On wide screens the panel is always visible: just bring it into view.
  if (matchMedia("(min-width: 1024px)").matches) { els.panel.scrollTop = 0; els.panel.querySelector("button, a")?.focus(); return; }
  openDrawer(els.panel, opener);
}

els.menu.addEventListener("click", () => openDrawer(els.sidebar, els.menu));
els.sidebarClose.addEventListener("click", () => closeDrawers());
els.panelToggle.addEventListener("click", () => openPanel(els.panelToggle));
els.panelClose.addEventListener("click", () => closeDrawers());
els.scrim.addEventListener("click", () => closeDrawers());
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawers(); });
// Leaving drawer mode (e.g. rotating a tablet) must not strand the scrim.
matchMedia("(min-width: 1280px)").addEventListener("change", () => closeDrawers(false));

const isPhone = () => matchMedia("(max-width: 767px)").matches;

function startNewChat() {
  newConversation(); renderAll(); closeDrawers(false);
  if (!isPhone()) els.input.focus();  // on phones focusing would pop the keyboard over the home screen
}
els.newChat.addEventListener("click", startNewChat);
els.newChatTop.addEventListener("click", startNewChat);

/* --------------------------------------------------------------- display settings */
function applyTextSize(i) {
  const [val, key] = TEXT_SIZES[i];
  if (val) document.documentElement.dataset.text = val; else delete document.documentElement.dataset.text;
  els.textSize.setAttribute("aria-label", t("textSizeAria", { size: t(key) }));
  els.textSize.querySelector(".tool-label").textContent = i ? t("textSizeLabel", { size: t(key) }) : t("textSize");
  els.textSize.setAttribute("aria-pressed", String(i > 0));
}
els.textSize.addEventListener("click", () => {
  const i = (Number(pref("dsa_text") || 0) + 1) % TEXT_SIZES.length;
  pref("dsa_text", String(i));
  applyTextSize(i);
});
function applyContrast(on) {
  if (on) document.documentElement.dataset.contrast = "high"; else delete document.documentElement.dataset.contrast;
  els.contrast.setAttribute("aria-pressed", String(on));
}
els.contrast.addEventListener("click", () => {
  const on = els.contrast.getAttribute("aria-pressed") !== "true";
  pref("dsa_contrast", on ? "1" : "0");
  applyContrast(on);
});

/* --------------------------------------------------------------- home screen */
function buildHome() {
  els.topics.innerHTML = "";
  for (const topic of t("topics")) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "topic";
    b.innerHTML = `<span class="topic-icon">${icon(topic.icon)}</span>
      <span class="topic-name">${escapeHtml(topic.name)}</span>
      <span class="topic-hint">${escapeHtml(topic.hint)}</span>`;
    b.onclick = () => send(topic.q);
    els.topics.appendChild(b);
  }
  els.suggestions.innerHTML = "";
  for (const s of t("examples")) {
    const b = document.createElement("button");
    b.className = "example"; b.type = "button"; b.textContent = s;
    b.onclick = () => send(s);
    els.suggestions.appendChild(b);
  }
  els.langChips.innerHTML = "";
  for (const code of HOME_LANGS) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "lang-chip";
    b.dataset.lang = code;
    b.textContent = code === "auto" ? t("autoChip") : NATIVE[code];
    if (code === "auto") b.setAttribute("aria-label", t("autoChipAria"));
    b.onclick = () => setLanguage(code);
    els.langChips.appendChild(b);
  }
  const more = document.createElement("button");
  more.type = "button";
  more.className = "lang-chip";
  more.textContent = t("moreChip");
  more.setAttribute("aria-label", t("moreChipAria"));
  more.onclick = () => {
    if (!matchMedia("(min-width: 1280px)").matches) openDrawer(els.sidebar, more);
    els.lang.focus();
  };
  els.langChips.appendChild(more);
  syncLangChips();
}

function setLanguage(code) {
  els.lang.value = [...els.lang.options].some((o) => o.value === code) ? code : "auto";
  pref("dsa_lang", els.lang.value);
  if (code === "hi" || code === "en") pref("dsa_ui", code);
  applyUiLanguage();
}

/* --------------------------------------------------------------- interface language */
// हिन्दी chosen -> Hindi interface. Another language -> English interface (the
// answers still come in that language). Auto -> what the user last wrote in,
// else the phone's own language.
function chooseUiLang() {
  const sel = els.lang.value;
  if (sel === "hi") return "hi";
  if (sel !== "auto") return "en";
  const saved = pref("dsa_ui");
  if (saved === "hi" || saved === "en") return saved;
  return /^hi\b/i.test(navigator.language || "") ? "hi" : "en";
}

function applyUiLanguage(lang = chooseUiLang()) {
  UI_LANG = lang;
  translatePage();
  // Generated parts, and texts that depend on state, are rebuilt here. The chat
  // itself is not re-rendered, so an answer being read aloud keeps playing.
  buildHome();
  renderSidebar();
  renderInsights();
  renderDoc();
  refreshGetApp();
  setMicState(isRecording());
  applyTextSize(Number(pref("dsa_text") || 0) % TEXT_SIZES.length);
  els.chat.querySelectorAll(".matches-pill").forEach((pill) => {
    pill.querySelector("span").textContent = pillText(Number(pill.dataset.count));
  });
}
function syncLangChips() {
  els.langChips.querySelectorAll("[data-lang]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.lang === els.lang.value)));
}
els.lang.addEventListener("change", () => setLanguage(els.lang.value));

async function loadLanguages() {
  let langs = null;
  try {
    const res = await fetch("/api/health");
    langs = (await res.json()).languages;
  } catch { /* fall back to the built-in list */ }
  const entries = langs ? Object.entries(langs) : Object.keys(NATIVE).map((c) => [c, c]);
  for (const [name, code] of entries) {
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = NATIVE[code] && NATIVE[code] !== name ? `${NATIVE[code]} (${name})` : name;
    els.lang.appendChild(opt);
  }
}

/* --------------------------------------------------------------- installable app */
// The service worker makes the site installable and lets it open offline.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

// Chrome/Edge/Android offer installation through `beforeinstallprompt`. Show
// our own buttons (top bar + "Get the app" card on the home screen), since many
// people never find "Add to Home screen" in the browser menu. iPhones have no
// such event, so the card explains Share -> Add to Home Screen instead.
// (Elements are looked up defensively: right after an update a browser can
// briefly pair a cached older page with this newer script.)
let installPrompt = null;
const installButtons = [$("#install-btn"), $("#get-app-install")].filter(Boolean);
const getApp = $("#get-app");
const isInstalled = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent)
  || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const isAndroid = /android/i.test(navigator.userAgent);

function refreshGetApp() {
  const how = $("#get-app-how");
  if (how) how.textContent = t(installPrompt ? "getAppReady" : isIOS ? "getAppIOS" : "getAppMenu");
}

function setupGetApp() {
  if (!getApp || isInstalled()) return;  // already running as the installed app
  refreshGetApp();
  getApp.hidden = false;
  // Offer the downloadable APK on Android once one has been published.
  if (isAndroid) {
    fetch("/api/app-info").then((r) => r.json()).then((info) => {
      const link = $("#get-app-apk");
      if (info.apk && link) { link.href = info.apk; link.hidden = false; }
    }).catch(() => {});
  }
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  installPrompt = e;
  installButtons.forEach((b) => { b.hidden = false; });
  refreshGetApp();
});
installButtons.forEach((b) => b.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice.catch(() => {});
  installPrompt = null;
  installButtons.forEach((btn) => { btn.hidden = true; });
}));
window.addEventListener("appinstalled", () => {
  installButtons.forEach((b) => { b.hidden = true; });
  if (getApp) getApp.hidden = true;
});

/* --------------------------------------------------------------- init */
window.addEventListener("DOMContentLoaded", async () => {
  if (window.marked) window.marked.setOptions({ breaks: true });
  applyTextSize(Number(pref("dsa_text") || 0) % TEXT_SIZES.length);
  applyContrast(pref("dsa_contrast") === "1");
  if (pref("dsa_tts") === "0") els.tts.click();
  if (matchMedia("(max-width: 479px)").matches) els.input.dataset.i18nPh = "placeholderShort";
  UI_LANG = chooseUiLang();   // first paint in the right language (the select is still "auto")
  translatePage();
  buildHome();
  setupGetApp();
  renderAll();
  await loadLanguages();
  setLanguage(pref("dsa_lang") || "auto");
  if (!isPhone()) els.input.focus();
});
