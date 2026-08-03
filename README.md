# ♿ Disability Schemes Chatbot

An empathetic, accessible AI assistant that helps persons with disabilities in India find the government welfare schemes they qualify for. Ask by **text or voice, in any Indian language** — the assistant detects the language automatically, answers from official government sources only, and reads the answer back aloud.

Built on a Hybrid Search RAG pipeline (FAISS + BM25 + FlashRank reranking) with a **FastAPI backend and a modern vanilla-JS chat interface**.

---

## 🌟 Features

**Intelligence**
- **Hybrid retrieval** — semantic (FAISS, 70%) + keyword (BM25, 30%), then FlashRank reranking.
- **Zero-hallucination guardrails** — answers only from scraped official sources; never invents amounts or user details.
- **Adaptive conversation** — never re-asks a detail you already gave; asks follow-ups only when genuinely needed.
- **Dynamic follow-up suggestions** — 3–5 contextual, clickable questions generated after every answer, adapting as the topic changes.
- **Document Q&A** — upload a PDF/TXT and ask questions about it.

**Voice & language**
- **Automatic language detection** — no manual selection required, ever.
- **Speech-to-text** via Groq **Whisper large-v3** (auto-detects language, handles code-switching, noise-robust).
- **Text-to-speech** via gTTS, spoken in *your* language, with Markdown stripped so it never reads "asterisk asterisk".
- **13 languages**: English, Hindi, Tamil, Telugu, Marathi, Bengali, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu.

**Interface & accessibility**
- Streaming token-by-token responses with a typing indicator.
- Multi-conversation sidebar, Markdown rendering, code highlighting.
- Full keyboard navigation, ARIA labels, visible focus states, skip link, `prefers-reduced-motion` support.
- Responsive, with automatic light and dark themes.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn (SSE streaming) |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| LLM | Llama 3.1 8B via Groq *(swappable — see below)* |
| Speech-to-text | Groq Whisper `large-v3` |
| Text-to-speech | gTTS |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector store | FAISS (CUDA if available, else CPU) |
| Retrieval | LangChain `EnsembleRetriever` + `FlashrankRerank` |
| Translation | `deep-translator`, `langdetect` |
| Ingestion | `requests`, `beautifulsoup4`, `pypdf` |

---

## 🚀 Setup

```bash
git clone <repository-url>
cd disability-schemes-chatbot

python -m venv venv
venv\Scripts\activate          # Windows  (source venv/bin/activate on macOS/Linux)

pip install -r requirements.txt
cp .env.example .env           # then add your GROQ_API_KEY
```

Build the knowledge base and vector index (first run only):

```bash
python scripts/update_all.py   # or double-click run_updates.bat on Windows
```

**Run the app:**

```bash
python -m uvicorn server.main:app --port 8000
```

Then open **http://localhost:8000**. Run from the project root — the pipeline loads the vector store from the relative path `scripts/vector_store`.

---

## 🔧 Choosing an LLM provider

The assistant is **not hard-locked to Groq**. Set `LLM_PROVIDER` in `.env`:

| Value | Uses | When to pick it |
|---|---|---|
| `groq` *(default)* | Groq cloud (`GROQ_MODEL`) | Fastest; needs `GROQ_API_KEY` |
| `ollama` | A **local** model, no internet | Groq unreachable, offline, or privacy-sensitive |
| `openai` | Any OpenAI-compatible endpoint | Using OpenAI or a self-hosted gateway |

**If Groq returns `403 — Access denied. Please check your network settings`,** you are almost certainly behind a **VPN or proxy** — Groq blocks VPN/datacenter IPs. Disconnect the VPN, or switch to a local model:

```bash
# 1. install Ollama from https://ollama.com
ollama pull llama3.1
# 2. in .env:
LLM_PROVIDER=ollama
```

---

## ⚙️ How it works

1. **Ingestion** — official portals and PDFs are scraped, structured into Markdown by an LLM, and embedded into FAISS.
2. **Input** — you type or speak; Whisper transcribes and detects the language automatically.
3. **Translation** — the question is translated to English for best retrieval quality.
4. **Hybrid retrieval** — FAISS (70%) + BM25 (30%), reranked by FlashRank; contact details are stripped so PIN/phone numbers are never mistaken for grant amounts.
5. **Generation** — Llama 3.1 answers under strict formatting and anti-hallucination rules, streamed token-by-token.
6. **Output** — the answer is translated back to your language, displayed as formatted Markdown with source citations, spoken aloud, and followed by contextual follow-up chips.

---

## 🗂️ Project layout

```
server/main.py          FastAPI API + static hosting
frontend/               index.html, style.css, app.js  (the UI)
chatbot/router.py       Intent classification + routing table
chatbot/rag_pipeline.py Routed retrieval, prompts, streaming, follow-ups, LLM provider
chatbot/voice_utils.py  Whisper STT + gTTS TTS + speech normalisation
chatbot/language_utils.py  Translation + language detection
scripts/                Scraper, embedder, orchestrator, tests
knowledge-base/         Scraped scheme Markdown + sources.json
```

### Intent routing

Every message is classified before anything else runs, so the assistant does the
right *kind* of work instead of treating everything as a document lookup:

| Intent | Retrieves? | History | Behaviour |
|---|---|---|---|
| `SCHEME_LOOKUP` | ✅ narrow | facts | Full sectioned layout for the best-fit few schemes |
| `LIST_ALL` | ✅ **broad** | facts | Enumerates **every** relevant scheme, not just the top few |
| `COMPARE` | ✅ **broad** | facts | Comparison table + a reasoned recommendation |
| `ELIGIBILITY` | ✅ narrow | facts | Verdict first, then deciding criteria |
| `RESOURCE_LINK` | ✅ narrow | none | Link first, no headings, never invents a URL |
| `WRITE_DOCUMENT` | ✅ narrow | facts | **Writes the actual letter/application**, with placeholders |
| `STEPS` | ✅ narrow | none | Only the numbered application procedure |
| `EXPLAIN` | ✅ narrow | none | Explains just that thing |
| `SUMMARIZE` | ❌ | full | Recaps the conversation |
| `SMALL_TALK` | ❌ | none | Brief friendly reply |
| `GENERAL` | ❌ | facts | Answers from the LLM's own reasoning |

Past assistant answers are **clipped** in history so the model cannot re-emit them —
the root cause of the old "every reply repeats the last one" behaviour.

`LIST_ALL` and `COMPARE` use a second, much wider retriever (`k=20`, rerank
`top_n=15`) instead of the default (`k=10`, rerank `top_n=3`) — the default was
silently capping *every* answer to 3 chunks regardless of intent, which is why
"list all schemes" and "which is better" used to just repeat one scheme's
template instead of surveying the knowledge base. A presentation request like
"put this in a table" is layered onto whichever intent was classified, rather
than being its own category.

### Link verification

The assistant never lets the LLM type a URL from memory. Every link it presents was
checked reachable moments earlier: candidate URLs come from the retrieved scheme's
full source file (not just the matched chunk), each is verified with a live
HEAD/GET request, and only verified URLs are placed in the prompt. A deterministic
backstop (`sanitize_answer_links`) strips anything else the model outputs anyway.
If nothing verifies, it tells the user honestly and names the official portal
instead of guessing — and a live web-search fallback (optional, needs
`TAVILY_API_KEY`) kicks in only for link requests, not every scheme lookup. See
[docs/backend_rag.md](docs/backend_rag.md#-link-verification-never-hallucinate-a-url).

---

## 📚 Documentation

| Guide | Contents |
|---|---|
| [docs/README.md](docs/README.md) | System overview and architecture diagram |
| [docs/project_brief.md](docs/project_brief.md) | Plain-language explanation of the whole project |
| [docs/frontend_ui.md](docs/frontend_ui.md) | FastAPI API, frontend, voice, accessibility |
| [docs/backend_rag.md](docs/backend_rag.md) | RAG retrieval, reranking, prompts, follow-ups |
| [docs/data_agents.md](docs/data_agents.md) | Scraping, indexing, automation, testing |

---

## 🤖 Automation

Two GitHub Actions keep the knowledge base fresh:
- **`auto_scrape.yml`** — monthly scrape → re-embed → commit.
- **`embed_on_push.yml`** — re-embeds whenever `knowledge-base/**` changes.

> `scripts/vector_store/` and `scripts/seen_hashes.json` **must stay un-ignored** in `.gitignore` — these workflows commit them back to the repo, and ignoring them makes `git-auto-commit-action` fail with `Invalid status code: 1`.

---

## 🧩 Supported disabilities

Visual impairment · Locomotor disability · Hearing impairment · Intellectual disability · Mental illness · Autism spectrum disorder · Cerebral palsy · Specific learning disability · Multiple disabilities

---

## 📞 Support helpline

Official national helpline: **1800-111-555**
