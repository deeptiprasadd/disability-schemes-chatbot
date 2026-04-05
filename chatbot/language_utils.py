
from deep_translator import GoogleTranslator

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
