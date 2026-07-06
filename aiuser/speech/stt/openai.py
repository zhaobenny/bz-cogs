from __future__ import annotations

from typing import Any

from redbot.core import Config
from redbot.core.bot import Red

from aiuser.llm.openai_compatible.client import setup_openai_client
from aiuser.speech.constants import OPENAI_API_V1_URL

DEFAULT_MODEL = "gpt-4o-mini-transcribe"


async def transcribe(
    bot: Red, config: Config, audio: bytes, audio_format: str, model: str
) -> str:
    client = await setup_openai_client(
        bot,
        config,
        base_url=OPENAI_API_V1_URL,
    )
    if client is None:
        raise ValueError("OpenAI API key is not configured")

    try:
        response: Any = await client.audio.transcriptions.create(
            file=(f"audio.{audio_format}", audio),
            model=model,
            response_format="json",
        )
    finally:
        await client.close()

    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise ValueError("OpenAI returned an empty transcript")
    return text
