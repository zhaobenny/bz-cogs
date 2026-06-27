import re

import httpx
from redbot.core.bot import Red

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.functions.context import ToolContext
from aiuser.functions.voice.constants import TTS_PROVIDER_TIMEOUT

INLINE_TAG_MODELS = {
    "google/gemini-3.1-flash-tts-preview",
    "x-ai/grok-voice-tts-1.0",
}

INLINE_TAG_RE = re.compile(r"\s*\[[A-Za-z][A-Za-z0-9_ :,.'-]{0,60}\]\s*")


def _strip_inline_tags(text: str) -> str:
    cleaned = INLINE_TAG_RE.sub(" ", text)
    return " ".join(cleaned.split()).strip()


async def generate(text: str, request: ToolContext) -> bytes:
    bot: Red = request.bot
    tokens = await bot.get_shared_api_tokens("openrouter")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("OpenRouter API key is not configured")

    guild_conf = request.config.guild(request.ctx.guild)
    model = await guild_conf.function_calling_voice_model()
    voice = await guild_conf.function_calling_voice()
    if not model:
        raise ValueError("OpenRouter voice model is not configured")
    if not voice:
        raise ValueError("OpenRouter voice is not configured")

    if model not in INLINE_TAG_MODELS:
        text = _strip_inline_tags(text)
        if not text:
            raise ValueError("Voice text only contained unsupported inline tags")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    async with httpx.AsyncClient(timeout=TTS_PROVIDER_TIMEOUT) as client:
        response = await client.post(
            f"{OPENROUTER_API_V1_URL}audio/speech",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        return response.content
