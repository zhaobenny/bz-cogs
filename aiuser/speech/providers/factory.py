from __future__ import annotations

from aiuser.speech.providers import openai, openrouter

OPENAI = "openai"
OPENROUTER = "openrouter"

PROVIDERS = {
    OPENAI: openai.transcribe,
    OPENROUTER: openrouter.transcribe,
}

DEFAULT_MODELS = {
    OPENAI: openai.DEFAULT_MODEL,
    OPENROUTER: openrouter.DEFAULT_MODEL,
}
