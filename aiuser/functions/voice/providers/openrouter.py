from io import BytesIO
import wave

import httpx
from redbot.core.bot import Red

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.functions.context import ToolContext
from aiuser.functions.voice.constants import (
    DEFAULT_OPENROUTER_TTS_MODEL,
    DEFAULT_OPENROUTER_TTS_VOICE,
    OPENROUTER_INLINE_TAG_MODELS,
    TTS_PROVIDER_TIMEOUT,
    strip_inline_tags,
)

DEFAULT_MODEL = DEFAULT_OPENROUTER_TTS_MODEL
DEFAULT_VOICE = DEFAULT_OPENROUTER_TTS_VOICE


def _pcm_to_wav(audio: bytes) -> bytes:
    wav = BytesIO()
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio)
    return wav.getvalue()


async def generate(text: str, request: ToolContext) -> bytes:
    bot: Red = request.bot
    tokens = await bot.get_shared_api_tokens("openrouter")
    api_key = tokens.get("api_key")
    if not api_key:
        raise ValueError("OpenRouter API key is not configured")

    guild_conf = request.config.guild(request.ctx.guild)
    model = await guild_conf.function_calling_voice_model() or DEFAULT_MODEL
    voice = await guild_conf.function_calling_voice() or DEFAULT_VOICE

    if model not in OPENROUTER_INLINE_TAG_MODELS:
        text = strip_inline_tags(text)
        if not text:
            raise ValueError("Voice text only contained unsupported inline tags")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
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
