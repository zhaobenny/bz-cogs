from __future__ import annotations

from typing import Optional

import httpx
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.providers.speech.constants import (
    ELEVENLAB_INLINE_TAG_MODELS,
    TTS_PROVIDER_TIMEOUT,
    strip_inline_tags,
)

ELEVENLAB_API_V1_URL = "https://api.elevenlabs.io/v1/"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


async def generate(
    bot: Red, config: Config, text: str, model: Optional[str], voice: Optional[str]
) -> bytes:
    tokens = await bot.get_shared_api_tokens("elevenlab")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("ElevenLab API key is not configured")

    model = model or DEFAULT_MODEL
    if model not in ELEVENLAB_INLINE_TAG_MODELS:
        text = strip_inline_tags(text)
        if not text:
            raise ValueError("Voice text only contained unsupported inline tags")

    payload = {
        "text": text,
        "model_id": model,
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    params = {"output_format": DEFAULT_OUTPUT_FORMAT}

    async with httpx.AsyncClient(timeout=TTS_PROVIDER_TIMEOUT) as client:
        response = await client.post(
            f"{ELEVENLAB_API_V1_URL}text-to-speech/{voice or DEFAULT_VOICE}",
            json=payload,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.content
