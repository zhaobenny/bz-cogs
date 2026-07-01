from __future__ import annotations

from aiuser.speech.providers import openrouter

OPENROUTER = "openrouter"

PROVIDERS = {
    OPENROUTER: openrouter.transcribe,
}
