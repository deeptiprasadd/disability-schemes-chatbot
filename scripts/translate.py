from deep_translator import GoogleTranslator

SUPPORTED_LANGUAGES = {
    "Hindi":      "hi",
    "Tamil":      "ta",
    "Telugu":     "te",
    "Marathi":    "mr",
    "Bengali":    "bn",
    "Gujarati":   "gu",
    "Kannada":    "kn",
    "Malayalam":  "ml",
    "Punjabi":    "pa",
    "English":    "en"
}

def detect_and_translate_to_english(text: str) -> tuple[str, str]:
    """Returns (english_text, detected_lang_code)"""
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(text)
        detected   = GoogleTranslator(source="auto", target="en").source
        return translated, detected or "en"
    except Exception:
        return text, "en"

def translate_to_language(text: str, lang_code: str) -> str:
    """Translate English response back to user's language"""
    if lang_code == "en":
        return text
    try:
        return GoogleTranslator(source="en", target=lang_code).translate(text)
    except Exception:
        return text
