import time

from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory

# Make langdetect deterministic across runs (it is randomized by default).
DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {
    "English":   "en",
    "Hindi":     "hi",
    "Tamil":     "ta",
    "Telugu":    "te",
    "Marathi":   "mr",
    "Bengali":   "bn",
    "Gujarati":  "gu",
    "Kannada":   "kn",
    "Malayalam": "ml",
    "Punjabi":   "pa",
    "Odia":      "or",
    "Assamese":  "as",
    "Urdu":      "ur"
}

# Each language's own name, so prompts can say "write in हिन्दी (Hindi)".
NATIVE_NAMES = {
    "en": "English", "hi": "हिन्दी", "ta": "தமிழ்", "te": "తెలుగు", "mr": "मराठी",
    "bn": "বাংলা", "gu": "ગુજરાતી", "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "pa": "ਪੰਜਾਬੀ",
    "or": "ଓଡ଼ିଆ", "as": "অসমীয়া", "ur": "اردو",
}
_CODE_TO_NAME = {code: name for name, code in SUPPORTED_LANGUAGES.items()}

# The free Google endpoint rejects requests over ~5000 characters and rate-limits
# bursts. Either failure used to fall back SILENTLY to English, which is why a
# long Hindi answer could arrive in English while the short follow-up chips were
# translated fine.
_MAX_CHARS = 4500


def language_name(lang_code: str) -> str:
    """'hi' -> 'Hindi'. Unknown codes -> 'English'."""
    return _CODE_TO_NAME.get(lang_code or "en", "English")


def _translate(text: str, source: str, target: str) -> str:
    """Translate in paragraph-aligned chunks, retrying once on a transient failure."""
    chunks, current = [], ""
    for para in text.split("\n"):
        if current and len(current) + len(para) + 1 > _MAX_CHARS:
            chunks.append(current)
            current = ""
        current = f"{current}\n{para}" if current else para
    chunks.append(current)

    out = []
    for chunk in chunks:
        if not chunk.strip():
            out.append(chunk)
            continue
        for attempt in range(2):
            try:
                out.append(GoogleTranslator(source=source, target=target).translate(chunk) or chunk)
                break
            except Exception:
                if attempt:
                    raise
                time.sleep(1.5)  # "too many requests" clears after a moment
    return "\n".join(out)


def translate_to_english(text: str) -> tuple:
    """
    Translates any language text to English.
    Returns (translated_text, True), or (text, False) when the service failed —
    callers can then fall back to another translator instead of guessing.
    """
    try:
        return _translate(text, "auto", "en"), True
    except Exception as e:
        print(f"Translation to English failed: {e}")
        return text, False


def translate_to_language(text: str, lang_code: str) -> str:
    """
    Translates English text to the user's language.
    Returns the original text if lang_code is 'en' or translation fails.
    """
    if not lang_code or lang_code == "en":
        return text
    try:
        return _translate(text, "en", lang_code)
    except Exception as e:
        print(f"Translation to {lang_code} failed: {e}")
        return text


def get_language_code(language_name: str) -> str:
    """Returns language code from display name. Defaults to 'en'."""
    return SUPPORTED_LANGUAGES.get(language_name, "en")


def detect_language(text: str) -> str:
    """
    Best-effort ISO-639-1 detection for typed text, limited to the languages we
    support; anything else (Hinglish often detects as e.g. 'id'), empty input,
    or a detection failure returns 'en'. For voice the language comes from
    Whisper instead, which is more reliable.
    """
    if not text or not text.strip():
        return "en"
    try:
        # langdetect can return region-tagged codes like 'zh-cn'; keep the base.
        code = detect(text).split("-")[0]
    except Exception:
        return "en"
    return code if code in _CODE_TO_NAME else "en"
