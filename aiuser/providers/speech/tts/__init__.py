from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord
from redbot.core import Config

from aiuser.providers.speech.constants import ELEVENLAB, FINEVOICE, OPENAI, OPENROUTER
from aiuser.providers.speech.tts import elevenlab, finevoice, openai, openrouter

PROVIDERS = {
    ELEVENLAB: elevenlab.generate,
    FINEVOICE: finevoice.generate,
    OPENAI: openai.generate,
    OPENROUTER: openrouter.generate,
}

DEFAULT_MODELS = {
    ELEVENLAB: elevenlab.DEFAULT_MODEL,
    FINEVOICE: None,
    OPENAI: openai.DEFAULT_MODEL,
    OPENROUTER: openrouter.DEFAULT_MODEL,
}

DEFAULT_VOICES = {
    ELEVENLAB: elevenlab.DEFAULT_VOICE,
    FINEVOICE: finevoice.DEFAULT_VOICE,
    OPENAI: openai.DEFAULT_VOICE,
    OPENROUTER: openrouter.DEFAULT_VOICE,
}


@dataclass(frozen=True)
class VoiceSettings:
    provider: str
    model: Optional[str]
    voice: Optional[str]


async def voice_settings(config: Config, guild: discord.Guild) -> VoiceSettings:
    """Resolve the guild's TTS settings, applying per-provider defaults."""
    guild_conf = config.guild(guild)
    provider = (
        (await guild_conf.function_calling_voice_provider() or FINEVOICE)
        .strip()
        .lower()
    )
    model = await guild_conf.function_calling_voice_model() or DEFAULT_MODELS.get(
        provider
    )
    voice = await guild_conf.function_calling_voice() or DEFAULT_VOICES.get(provider)
    return VoiceSettings(provider, model, voice)
