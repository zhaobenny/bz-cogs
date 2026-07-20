from __future__ import annotations

import base64

import httpx
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.config.constants import OPENROUTER_API_V1_URL

TRANSCRIPTION_TIMEOUT = 30
DEFAULT_MODEL = "openai/whisper-large-v3"


async def transcribe(
    bot: Red, config: Config, audio: bytes, audio_format: str, model: str
) -> str:
    tokens = await bot.get_shared_api_tokens("openrouter")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("OpenRouter API key is not configured")

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=TRANSCRIPTION_TIMEOUT) as client:
        response = await client.post(
            f"{OPENROUTER_API_V1_URL}audio/transcriptions",
            json={
                "model": model,
                "input_audio": {
                    "data": base64.b64encode(audio).decode("ascii"),
                    "format": audio_format,
                },
            },
            headers=headers,
        )
        response.raise_for_status()

    data = response.json()
    text = str(data.get("text") or "").strip()
    if not text:
        raise ValueError("OpenRouter returned an empty transcript")
    return text
