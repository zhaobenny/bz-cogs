from __future__ import annotations

import asyncio
from typing import Optional

import httpx
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.speech.constants import TTS_PROVIDER_TIMEOUT

FINEVOICE_API_V1_URL = "https://apis.finevoice.ai/v1/"
TTS_POLL_INTERVAL = 5
DEFAULT_VOICE = "james"


async def generate(
    bot: Red, config: Config, text: str, model: Optional[str], voice: Optional[str]
) -> bytes:
    tokens = await bot.get_shared_api_tokens("finevoice")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("FineVoice API key is not configured")

    payload = {
        "voice": voice or DEFAULT_VOICE,
        "text": text,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=TTS_PROVIDER_TIMEOUT) as client:
        response = await client.post(
            f"{FINEVOICE_API_V1_URL}audio/speech-synthesis",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        audio_result = data.get("url") or next(iter(data.get("urls") or []), None)
        task_id = data.get("taskId")

        for _ in range(TTS_PROVIDER_TIMEOUT // TTS_POLL_INTERVAL):
            if not task_id:
                break
            await asyncio.sleep(TTS_POLL_INTERVAL)
            response = await client.get(
                f"{FINEVOICE_API_V1_URL}task/{task_id}",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            audio_result = data.get("url") or next(iter(data.get("urls") or []), None)
            if audio_result:
                break

        if not audio_result:
            raise ValueError("FineVoice response did not include an audio URL")

        audio = await client.get(audio_result)
        audio.raise_for_status()
        return audio.content
