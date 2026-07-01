import re

MAX_VOICE_WORDS = 75
TTS_PROVIDER_TIMEOUT = 45

ELEVENLAB = "elevenlab"
FINEVOICE = "finevoice"
OPENROUTER = "openrouter"

DEFAULT_ELEVENLAB_MODEL = "eleven_multilingual_v2"
DEFAULT_ELEVENLAB_VOICE = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_FINEVOICE_VOICE = "james"
DEFAULT_OPENROUTER_TTS_MODEL = "x-ai/grok-voice-tts-1.0"
DEFAULT_OPENROUTER_TTS_VOICE = "Eve"

INLINE_TAG_RE = re.compile(r"\s*\[[A-Za-z][A-Za-z0-9_ :,.'-]{0,60}\]\s*")
ELEVENLAB_INLINE_TAG_MODELS = {"eleven_v3"}
OPENROUTER_INLINE_TAG_MODELS = {
    "google/gemini-3.1-flash-tts-preview",
    "x-ai/grok-voice-tts-1.0",
}


def strip_inline_tags(text: str) -> str:
    cleaned = INLINE_TAG_RE.sub(" ", text)
    return " ".join(cleaned.split()).strip()
