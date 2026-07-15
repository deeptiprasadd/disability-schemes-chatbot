"""
Voice utilities for the Disability Schemes Assistant.

Two responsibilities, kept free of any Streamlit imports so they can be unit
tested and reused:

  * Speech-to-Text (STT) with AUTOMATIC language detection, via Groq Whisper
    (`whisper-large-v3`). Whisper detects the spoken language on its own and
    handles code-switching (mixed-language speech) far better than the browser
    Web Speech API, which requires the language to be fixed up front.

  * Text-to-Speech (TTS) via gTTS, which covers the major Indian languages with
    no extra API key. Languages gTTS cannot speak (currently Odia/Assamese)
    return None so the caller can degrade gracefully instead of mispronouncing.

Upgrade path: swap `synthesize_speech` for Azure/Google Cloud/ElevenLabs for
premium neural voices and full Odia/Assamese coverage (needs a paid key).
"""

import io
import os

from dotenv import load_dotenv
from gtts import gTTS
from groq import Groq

load_dotenv()

# Whisper's `language` field comes back as an English NAME (e.g. "hindi") on
# Groq, but we map to ISO-639-1 codes used everywhere else (translation, TTS).
_WHISPER_LANG_TO_CODE = {
    "english": "en", "hindi": "hi", "tamil": "ta", "telugu": "te",
    "marathi": "mr", "bengali": "bn", "gujarati": "gu", "kannada": "kn",
    "malayalam": "ml", "punjabi": "pa", "oriya": "or", "odia": "or",
    "assamese": "as", "urdu": "ur", "nepali": "ne", "sanskrit": "sa",
}

# Languages gTTS can actually synthesize. Odia (or) / Assamese (as) are NOT
# supported, so we return no audio for them rather than speak them wrongly.
GTTS_SUPPORTED = {"en", "hi", "ta", "te", "mr", "bn", "gu", "kn", "ml", "pa", "ur"}

_client = None


def _groq() -> Groq:
    """Lazily create a single Groq client (reads GROQ_API_KEY from env)."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> tuple:
    """
    Transcribe recorded speech to text with automatic language detection.

    Returns (text, lang_code). On any failure or empty input returns ("", None)
    so callers can show a friendly retry message instead of crashing.
    """
    if not audio_bytes:
        return "", None
    try:
        resp = _groq().audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3",   # most accurate multilingual Whisper on Groq
            response_format="verbose_json",  # needed to read the detected language
            temperature=0.0,
        )
        text = (getattr(resp, "text", "") or "").strip()
        raw_lang = (getattr(resp, "language", "") or "").strip().lower()
        # Accept either an English name ("hindi") or an ISO code ("hi").
        code = _WHISPER_LANG_TO_CODE.get(raw_lang) or (raw_lang[:2] if raw_lang else None)
        return text, (code or None)
    except Exception as e:  # network / auth / bad audio -> degrade gracefully
        print(f"[voice] STT failed: {e}")
        return "", None


def synthesize_speech(text: str, lang_code: str) -> bytes | None:
    """
    Convert `text` into spoken MP3 bytes in `lang_code` using gTTS.

    Returns MP3 bytes, or None when the text is empty, the language is not
    supported by gTTS, or synthesis fails. Returning None (rather than falling
    back to an English voice) avoids reading, say, Odia text with English
    phonetics.
    """
    if not text or not text.strip():
        return None
    code = (lang_code or "en").lower()
    if code not in GTTS_SUPPORTED:
        return None
    try:
        buf = io.BytesIO()
        gTTS(text=text, lang=code, slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"[voice] TTS failed for lang={code}: {e}")
        return None
