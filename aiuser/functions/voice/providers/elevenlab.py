import httpx
from redbot.core.bot import Red

from aiuser.functions.context import ToolContext
from aiuser.functions.voice.constants import (
    DEFAULT_ELEVENLAB_MODEL,
    DEFAULT_ELEVENLAB_VOICE,
    TTS_PROVIDER_TIMEOUT,
)

ELEVENLAB_API_V1_URL = "https://api.elevenlabs.io/v1/"
DEFAULT_MODEL = DEFAULT_ELEVENLAB_MODEL
DEFAULT_VOICE = DEFAULT_ELEVENLAB_VOICE
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


async def generate(text: str, request: ToolContext) -> bytes:
    bot: Red = request.bot
    tokens = await bot.get_shared_api_tokens("elevenlab")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("ElevenLab API key is not configured")

    guild_conf = request.config.guild(request.ctx.guild)
    voice = await guild_conf.function_calling_voice() or DEFAULT_VOICE
    model = await guild_conf.function_calling_voice_model() or DEFAULT_MODEL

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
            f"{ELEVENLAB_API_V1_URL}text-to-speech/{voice}",
            json=payload,
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.content
