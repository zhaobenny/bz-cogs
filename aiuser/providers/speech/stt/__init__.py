from __future__ import annotations

from dataclasses import dataclass

import discord
from redbot.core import Config

from aiuser.config.defaults import (
    DEFAULT_AUDIO_DURATION_LIMIT,
    DEFAULT_STT_PROVIDER,
)
from aiuser.providers.speech.constants import OPENAI, OPENROUTER
from aiuser.providers.speech.stt import openai, openrouter

PROVIDERS = {
    OPENAI: openai.transcribe,
    OPENROUTER: openrouter.transcribe,
}

DEFAULT_MODELS = {
    OPENAI: openai.DEFAULT_MODEL,
    OPENROUTER: openrouter.DEFAULT_MODEL,
}


@dataclass(frozen=True)
class TranscriptionSettings:
    provider: str
    model: str
    max_duration: int


async def transcription_settings(
    config: Config, guild: discord.Guild
) -> TranscriptionSettings:
    """Resolve the guild's STT settings, applying defaults."""
    guild_conf = config.guild(guild)
    provider = (
        (await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER).strip().lower()
    )
    model = await guild_conf.scan_audio_model() or DEFAULT_MODELS.get(provider)
    max_duration = int(
        await guild_conf.max_audio_duration() or DEFAULT_AUDIO_DURATION_LIMIT
    )
    return TranscriptionSettings(provider, model, max_duration)
