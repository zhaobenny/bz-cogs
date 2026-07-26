from __future__ import annotations

import wave
from io import BytesIO
from typing import Optional

import httpx
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.providers.speech.constants import (
    OPENROUTER_INLINE_TAG_MODELS,
    TTS_PROVIDER_TIMEOUT,
    strip_inline_tags,
)

DEFAULT_MODEL = "x-ai/grok-voice-tts-1.0"
DEFAULT_VOICE = "Eve"


def _pcm_to_wav(audio: bytes) -> bytes:
    wav = BytesIO()
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio)
    return wav.getvalue()


async def generate(
    bot: Red, config: Config, text: str, model: Optional[str], voice: Optional[str]
) -> bytes:
    tokens = await bot.get_shared_api_tokens("openrouter")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("OpenRouter API key is not configured")

    model = model or DEFAULT_MODEL
    if model not in OPENROUTER_INLINE_TAG_MODELS:
        text = strip_inline_tags(text)
        if not text:
            raise ValueError("Voice text only contained unsupported inline tags")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "input": text,
        "voice": voice or DEFAULT_VOICE,
    }

    async with httpx.AsyncClient(timeout=TTS_PROVIDER_TIMEOUT) as client:
        response = await client.post(
            f"{OPENROUTER_API_V1_URL}audio/speech",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        if response.headers.get("content-type", "").split(";")[0] == "audio/pcm":
            return _pcm_to_wav(response.content)
        return response.content
