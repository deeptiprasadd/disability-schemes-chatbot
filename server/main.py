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
GET  /api/health      Liveness + whether the LLM is reachable.
GET  /                Static single-page front end.
"""

import io
import json
import os

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Reuse the existing, tested pipeline + helpers unchanged.
from chatbot.rag_pipeline import ask_stream, get_sources
from chatbot.language_utils import (
    translate_to_english,
    translate_to_language,
    detect_language,
    SUPPORTED_LANGUAGES,
)
from chatbot.voice_utils import transcribe_audio, synthesize_speech, GTTS_SUPPORTED

app = FastAPI(title="Disability Schemes Assistant API")

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


# --------------------------------------------------------------------------- helpers
def _sse(payload: dict) -> str:
    """Encode one Server-Sent Event."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# --------------------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return {"status": "ok", "languages": SUPPORTED_LANGUAGES}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """
    Stream the answer as SSE. We stream the English generation token-by-token
    for a live typing effect, then emit a final event carrying the answer
    translated into the user's language plus the source citations.
    """
    def generate():
        try:
            english_q, _ = translate_to_english(req.message)
            target = req.lang if req.lang and req.lang != "auto" else detect_language(req.message)

            history = [m.model_dump() for m in req.history]
            parts: list[str] = []
            for token in ask_stream(english_q, chat_history=history, extra_context=req.doc_text):
                parts.append(token)
                yield _sse({"type": "token", "text": token})

            english_answer = "".join(parts)
            translated = translate_to_language(english_answer, target)
            yield _sse({
                "type": "final",
                "answer": translated,
                "english": english_answer,
                "sources": get_sources(english_q),
                "lang": target,
                "tts_available": target in GTTS_SUPPORTED,
            })
        except Exception as e:  # surface a clean error to the client
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Speech -> text with automatic language detection (Groq Whisper)."""
    data = await file.read()
    text, lang = transcribe_audio(data, filename=file.filename or "audio.webm")
    return {"text": text, "lang": lang}


@app.post("/api/tts")
def tts(req: TTSRequest):
    """Text -> spoken MP3. Returns 204 when the language has no TTS voice."""
    audio = synthesize_speech(req.text, req.lang)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF/TXT/MD for use as context."""
    data = await file.read()
    name = file.filename or "document"
    try:
        if name.lower().endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        else:
            text = data.decode("utf-8", "ignore")
    except Exception as e:
        return {"name": name, "text": "", "chars": 0, "error": str(e)}
    return {"name": name, "text": text, "chars": len(text)}


# Static front end mounted last so the /api/* routes above take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
