"""
FastAPI backend for the Disability Schemes Assistant.

Exposes the existing RAG pipeline + voice utilities over a small HTTP API and
serves the vanilla JS front end. Run from the PROJECT ROOT (the RAG pipeline
loads the vector store from the relative path ``scripts/vector_store``):

    venv\\Scripts\\python -m uvicorn server.main:app --port 8000

Endpoints
---------
POST /api/chat        Server-Sent Events stream of the answer.
POST /api/transcribe  Audio file -> {text, lang}  (Groq Whisper, auto-detect).
POST /api/tts         {text, lang} -> audio/mpeg  (gTTS).
POST /api/upload      PDF/TXT/MD file -> {name, text, chars}.
POST /api/insights    User profile + matched schemes for the side panel.
GET  /api/health      Liveness + whether the LLM is reachable.
GET  /                Static single-page front end.
"""

import io
import json
import os
import threading
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Reuse the existing, tested pipeline + helpers unchanged.
from chatbot.rag_pipeline import (
    ask_stream, get_source_paths, generate_followups, route_for, to_english, is_romanized,
)
from chatbot.insights import build_insights, source_links
from chatbot.link_utils import sanitize_answer_links
from chatbot.kb_utils import drop_empty_sections
from chatbot.language_utils import (
    translate_to_language,
    detect_language,
    SUPPORTED_LANGUAGES,
)
from chatbot.voice_utils import transcribe_audio, synthesize_speech, GTTS_SUPPORTED

from chatbot import rag_pipeline
from server import guard


def _warm_up():
    """Load the search index and models before the first visitor needs them (~30 s)."""
    try:
        rag_pipeline.load_pipeline()
    except Exception as e:
        print(f"[startup] warm-up failed, will load on first request: {e}")


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Disability Schemes Assistant API", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    return response


def _too_many() -> JSONResponse:
    return JSONResponse({"error": guard.TOO_MANY}, status_code=429)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


# --------------------------------------------------------------------------- models
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    lang: str = "auto"          # "auto" or an ISO-639-1 code to force the reply language
    doc_text: str | None = None  # optional uploaded-document context


class TTSRequest(BaseModel):
    text: str
    lang: str = "en"


class FollowupRequest(BaseModel):
    question: str               # the English question, for best LLM quality
    answer: str                 # the answer as shown to the user
    history: list[Message] = []
    lang: str = "en"            # language to present the suggestions in


class InsightsRequest(BaseModel):
    question: str               # the English question
    history: list[Message] = []
    lang: str = "en"            # language for benefit / reason text


# --------------------------------------------------------------------------- helpers
def _sse(payload: dict) -> str:
    """Encode one Server-Sent Event."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Plain-language messages for failures a user can see. The technical detail
# goes to the server log; the browser only gets the message and a short code.
ERROR_MESSAGES = {
    "model_not_found": "The assistant's AI model isn't available right now. "
                       "The site admin needs to update the model setting (GROQ_MODEL).",
    "auth": "The assistant isn't set up correctly: its AI service key was rejected. "
            "The site admin needs to check the API key.",
    "blocked": "The AI service can't be reached from this network. "
               "If you're using a VPN, turn it off and try again.",
    "rate_limit": "The assistant is getting too many questions right now. Wait a minute, then try again.",
    "too_long": "Your question or document is too long for the assistant. "
                "Try a shorter question or a smaller document.",
    "unreachable": "The assistant couldn't connect to its AI service. "
                   "Check the internet connection and try again.",
    "unknown": "Something went wrong while answering. Try again in a moment.",
}


def classify_error(e: Exception) -> str:
    """
    Map a provider exception to an ERROR_MESSAGES key. Works across Groq,
    OpenAI-compatible and Ollama clients by checking the HTTP status the SDKs
    attach (`status_code`) and falling back to the error text.
    """
    status = getattr(e, "status_code", None)
    text = f"{type(e).__name__} {e}".lower()
    if status == 404 or "model_not_found" in text or ("model" in text and "does not exist" in text):
        return "model_not_found"
    if status == 401 or "invalid api key" in text or "invalid_api_key" in text:
        return "auth"
    if status == 413 or "context_length" in text or "request too large" in text:
        return "too_long"
    if status == 429 or "rate limit" in text or "rate_limit" in text:
        return "rate_limit"
    if status == 403 or "access denied" in text:
        return "blocked"
    if any(k in text for k in ("connect", "timeout", "timed out", "unreachable")):
        return "unreachable"
    return "unknown"


def _reply_language(req: "ChatRequest") -> str:
    """
    Language to answer in when the user left it on Auto. A short reply such as
    "इंदौर, मध्य प्रदेश" is too little text to tell Hindi from Marathi (same
    script), and was answered in Marathi; judging it together with the user's
    previous messages keeps the conversation's language.
    """
    text = req.message
    if len(text.split()) < 6:
        earlier = [m.content for m in req.history if m.role == "user"][-2:]
        text = " ".join(earlier + [text])
    return detect_language(text)


def _error_event(e: Exception) -> str:
    """Log the full error for the developer; send the user a readable one."""
    traceback.print_exc()
    code = classify_error(e)
    return _sse({"type": "error", "code": code, "message": ERROR_MESSAGES[code]})


# --------------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"status": "ok", "ready": rag_pipeline._chain is not None, "languages": SUPPORTED_LANGUAGES}


def _sse_error(code: str, message: str) -> StreamingResponse:
    return StreamingResponse(iter([_sse({"type": "error", "code": code, "message": message})]),
                             media_type="text/event-stream")


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    """
    Stream the answer as SSE, token by token, written directly in the user's
    language, then emit a final event carrying the link-checked answer plus the
    source citations.
    """
    if not guard.allow("chat", request):
        return _sse_error("too_many_requests", guard.TOO_MANY)
    if len(req.message) > guard.MAX_MESSAGE_CHARS:
        return _sse_error("too_long", f"Your message is too long. Keep it under "
                                      f"{guard.MAX_MESSAGE_CHARS} characters.")
    # Bound what a client can make us send to the LLM.
    req.history = [Message(role=m.role, content=m.content[:guard.MAX_HISTORY_CHARS])
                   for m in req.history[-guard.MAX_HISTORY_MESSAGES:]]
    req.doc_text = (req.doc_text or "")[:guard.MAX_DOC_CHARS] or None

    def generate():
        try:
            english_q = to_english(req.message)  # routing + retrieval work in English
            target = req.lang if req.lang and req.lang != "auto" else _reply_language(req)
            # "mujhe pension chahiye" detects as English; mirror it instead of answering in English.
            romanized = req.message if target == "en" and is_romanized(req.message, english_q) else None

            history = [m.model_dump() for m in req.history]

            # Classify once, then reuse: the route decides whether we retrieved,
            # and therefore whether citations are meaningful for this answer.
            route = route_for(english_q, history)

            link_result: dict = {}
            parts: list[str] = []
            for token in ask_stream(english_q, chat_history=history,
                                    extra_context=req.doc_text, route=route,
                                    result=link_result, reply_lang=target, romanized=romanized):
                parts.append(token)
                yield _sse({"type": "token", "text": token})

            answer = "".join(parts)
            # A URL can span several streamed tokens, so verification is applied
            # to the assembled text — this is why the client replaces the live
            # streamed text with the "final" event's answer.
            if route.needs_retrieval:
                answer = sanitize_answer_links(answer, link_result.get("verified_urls", set()))
            answer = drop_empty_sections(answer)  # "### Day care: No information available" adds nothing
            # The model writes in `target` directly. If it slipped into English
            # anyway, machine translation is the safety net.
            if target != "en" and detect_language(answer) == "en":
                answer = translate_to_language(answer, target)
            # No retrieval -> no citations, rather than misleading ones.
            paths = get_source_paths(english_q) if route.needs_retrieval else []
            yield _sse({
                "type": "final",
                "answer": answer,
                "english_question": english_q,
                "sources": [os.path.basename(p) for p in paths],
                "source_links": source_links(paths),  # [{name, url}] from front matter
                "intent": route.intent.value,
                "lang": target,
                "tts_available": target in GTTS_SUPPORTED,
            })
        except Exception as e:  # readable message for the user, full detail in the log
            yield _error_event(e)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _recent(history: list) -> list[dict]:
    return [{"role": m.role, "content": m.content[:guard.MAX_HISTORY_CHARS]}
            for m in history[-guard.MAX_HISTORY_MESSAGES:]]


@app.post("/api/followups")
def followups(req: FollowupRequest, request: Request):
    """
    Contextual follow-up questions for the latest turn. Called separately from
    /api/chat so the answer renders immediately and the chips arrive after.
    """
    if not guard.allow("extras", request):
        return {"followups": []}
    items = generate_followups(
        req.question[:guard.MAX_MESSAGE_CHARS], req.answer[:6000], _recent(req.history), lang=req.lang or "en"
    )
    return {"followups": items}


@app.post("/api/insights")
def insights(req: InsightsRequest, request: Request):
    """
    The user's stated profile and the schemes they match, for the side panel.
    Called after the answer renders, like /api/followups.
    """
    if not guard.allow("extras", request):
        return {"profile": [], "schemes": []}
    return build_insights(req.question[:guard.MAX_MESSAGE_CHARS], _recent(req.history), req.lang)


@app.post("/api/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)):
    """Speech -> text with automatic language detection (Groq Whisper)."""
    if not guard.allow("voice", request):
        return _too_many()
    data = await file.read(guard.MAX_AUDIO_BYTES + 1)
    if len(data) > guard.MAX_AUDIO_BYTES:
        return JSONResponse({"error": "That recording is too long. Keep voice questions under a minute."},
                            status_code=413)
    text, lang = transcribe_audio(data, filename=file.filename or "audio.webm")
    return {"text": text, "lang": lang}


@app.post("/api/tts")
def tts(req: TTSRequest, request: Request):
    """Text -> spoken MP3. Returns 204 when the language has no TTS voice."""
    if not guard.allow("tts", request):
        return _too_many()
    audio = synthesize_speech(req.text[:8000], req.lang)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF/TXT/MD for use as context."""
    if not guard.allow("upload", request):
        return _too_many()
    data = await file.read(guard.MAX_UPLOAD_BYTES + 1)
    name = file.filename or "document"
    if len(data) > guard.MAX_UPLOAD_BYTES:
        return JSONResponse({"name": name, "text": "", "chars": 0,
                             "error": "That file is too large. Upload a PDF or text file under 5 MB."},
                            status_code=413)
    try:
        if name.lower().endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        else:
            text = data.decode("utf-8", "ignore")
    except Exception as e:
        print(f"[upload] could not read {name!r}: {e}")
        return {"name": name, "text": "", "chars": 0,
                "error": "Couldn't read that file. Try a PDF with selectable text, or a .txt file."}
    return {"name": name, "text": text[:guard.MAX_DOC_CHARS], "chars": len(text)}


# Static front end mounted last so the /api/* routes above take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
