from __future__ import annotations

from redbot.core.bot import Red

from aiuser.functions.context import ToolContext
from aiuser.functions.voice.constants import (
    DEFAULT_OPENAI_TTS_MODEL,
    DEFAULT_OPENAI_TTS_VOICE,
    TTS_PROVIDER_TIMEOUT,
    strip_inline_tags,
)
from aiuser.llm.openai_compatible.client import setup_openai_client

OPENAI_API_V1_URL = "https://api.openai.com/v1"

DEFAULT_MODEL = DEFAULT_OPENAI_TTS_MODEL
DEFAULT_VOICE = DEFAULT_OPENAI_TTS_VOICE


async def generate(text: str, request: ToolContext) -> bytes:
    bot: Red = request.bot
    guild_conf = request.config.guild(request.ctx.guild)
    model = await guild_conf.function_calling_voice_model() or DEFAULT_MODEL
    voice = await guild_conf.function_calling_voice() or DEFAULT_VOICE

    text = strip_inline_tags(text)
    if not text:
        raise ValueError("Voice text only contained unsupported inline tags")

    client = await setup_openai_client(
        bot,
        request.config,
        base_url=OPENAI_API_V1_URL,
    )
    if client is None:
        raise ValueError("OpenAI API key is not configured")

    try:
        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
            timeout=TTS_PROVIDER_TIMEOUT,
        )
    finally:
        await client.close()

    return response.content
