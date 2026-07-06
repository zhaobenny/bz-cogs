import re

# provider names, as stored in config and shown in settings commands
ELEVENLAB = "elevenlab"
FINEVOICE = "finevoice"
OPENAI = "openai"
OPENROUTER = "openrouter"

TTS_PROVIDER_TIMEOUT = 45

# tone modifiers like [happy] that only some TTS models understand
INLINE_TAG_RE = re.compile(r"\s*\[[A-Za-z][A-Za-z0-9_ :,.'-]{0,60}\]\s*")
ELEVENLAB_INLINE_TAG_MODELS = {"eleven_v3"}
OPENROUTER_INLINE_TAG_MODELS = {
    "google/gemini-3.1-flash-tts-preview",
    "x-ai/grok-voice-tts-1.0",
}


def strip_inline_tags(text: str) -> str:
    cleaned = INLINE_TAG_RE.sub(" ", text)
    return " ".join(cleaned.split()).strip()
