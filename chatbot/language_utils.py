
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

def translate_to_english(text: str) -> tuple:
    """
    Translates any language text to English.
    Returns (translated_text, detected_lang_code)
    """
    try:
        translator   = GoogleTranslator(source="auto", target="en")
        translated   = translator.translate(text)
        detected     = translator.source if hasattr(translator, "source") else "en"
        return translated, detected or "en"
    except Exception as e:
        print(f"Translation to English failed: {e}")
        return text, "en"

def translate_to_language(text: str, lang_code: str) -> str:
    """
    Translates English text back to user's language.
    Returns original text if lang_code is 'en' or translation fails.
    """
    if not lang_code or lang_code == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=lang_code).translate(text)
    except Exception as e:
        print(f"Translation to {lang_code} failed: {e}")
        return text

def get_language_code(language_name: str) -> str:
    """Returns language code from display name. Defaults to 'en'."""
    return SUPPORTED_LANGUAGES.get(language_name, "en")

def detect_language(text: str) -> str:
    """
    Detect the language of `text`, returning an ISO-639-1 code.
    Only returns codes we support; anything else (or failure) falls back to 'en'.
    """
    try:
        code = detect(text)
        return code if code in SUPPORTED_LANGUAGES.values() else "en"
    except Exception:
        return "en"


def detect_language(text: str) -> str:
    """
    Best-effort ISO-639-1 language detection for typed text.

    Used when the user leaves the language on "Auto-detect" and types (rather
    than speaks). For voice, the language comes from Whisper instead, which is
    more reliable. Falls back to 'en' on empty input or detection failure.
    """
    if not text or not text.strip():
        return "en"
    try:
        # langdetect can return region-tagged codes like 'zh-cn'; keep the base.
        return detect(text).split("-")[0]
    except Exception:
        return "en"
