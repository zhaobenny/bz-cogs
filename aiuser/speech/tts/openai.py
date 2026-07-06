from __future__ import annotations

from typing import Optional

from redbot.core import Config
from redbot.core.bot import Red

from aiuser.llm.openai_compatible.client import setup_openai_client
from aiuser.speech.constants import OPENAI_API_V1_URL, TTS_PROVIDER_TIMEOUT, strip_inline_tags

DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"


async def generate(
    bot: Red, config: Config, text: str, model: Optional[str], voice: Optional[str]
) -> bytes:
    text = strip_inline_tags(text)
    if not text:
        raise ValueError("Voice text only contained unsupported inline tags")

    client = await setup_openai_client(
        bot,
        config,
        base_url=OPENAI_API_V1_URL,
    )
    if client is None:
        raise ValueError("OpenAI API key is not configured")

    try:
        response = await client.audio.speech.create(
            model=model or DEFAULT_MODEL,
            voice=voice or DEFAULT_VOICE,
            input=text,
            response_format="mp3",
            timeout=TTS_PROVIDER_TIMEOUT,
        )
    finally:
        await client.close()

    return response.content
