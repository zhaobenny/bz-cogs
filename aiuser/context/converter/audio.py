from __future__ import annotations

import asyncio
import logging
import shutil
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from discord import Message

from aiuser.config.defaults import (
    DEFAULT_AUDIO_DURATION_LIMIT,
    DEFAULT_STT_MODEL,
    DEFAULT_STT_PROVIDER,
)
from aiuser.functions.context import AUDIO_TRANSCRIPT_CACHE_NAMESPACE
from aiuser.speech.providers.factory import PROVIDERS

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.context")

SUPPORTED_AUDIO_FORMATS = {"wav", "mp3", "flac", "m4a", "ogg", "webm", "aac", "mp4"}
CONTENT_TYPE_FORMATS = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "video/mp4": "mp4",
}


def is_audio_attachment(message: Message) -> bool:
    if not message.attachments:
        return False
    attachment = message.attachments[0]
    if attachment.is_voice_message():
        return True

    content_type = (attachment.content_type or "").split(";")[0].lower()
    if content_type.startswith("audio/"):
        return True
    suffix = Path(attachment.filename or "").suffix.lstrip(".").lower()
    return suffix in SUPPORTED_AUDIO_FORMATS


def _format_audio_placeholder(message: Message) -> str:
    filename = message.attachments[0].filename
    if message.author.id == message.guild.me.id:
        return f'[Audio: "{filename}"]'
    return f'User "{message.author.display_name}" sent: [Audio: "{filename}"]'


async def format_audio(services: "AIUserServices", message: Message) -> str:
    transcript = services.context_cache[(AUDIO_TRANSCRIPT_CACHE_NAMESPACE, message.id)]
    return transcript or _format_audio_placeholder(message)


async def create_audio_transcript(
    services: "AIUserServices", message: Message
) -> Optional[str]:
    attachment = message.attachments[0]
    provider, model, max_duration = await _audio_transcription_options(
        services, message.guild
    )
    cache_key = (AUDIO_TRANSCRIPT_CACHE_NAMESPACE, message.id)
    cached = services.context_cache[cache_key]
    if cached:
        return cached

    gen_fn = PROVIDERS.get(provider)
    if gen_fn is None:
        return None

    content_type = (attachment.content_type or "").split(";")[0].lower()
    original_format = CONTENT_TYPE_FORMATS.get(content_type)
    if not original_format:
        suffix = Path(attachment.filename or "").suffix.lstrip(".").lower()
        if suffix in SUPPORTED_AUDIO_FORMATS:
            original_format = suffix
    if not original_format:
        return None

    buffer = BytesIO()
    await attachment.save(buffer)
    audio = buffer.getvalue()

    prepared_audio, prepared_format = await _trim_audio(audio, max_duration)
    if not prepared_audio:
        return None

    try:
        transcript = await gen_fn(
            services.bot,
            prepared_audio,
            prepared_format or original_format,
            model,
        )
    except ValueError:
        return None
    except Exception:
        logger.exception("Failed to transcribe audio attachment")
        return None

    if message.author.id == message.guild.me.id:
        content = f'[Voice message: "{transcript}"]'
    else:
        content = (
            f'User "{message.author.display_name}" sent: '
            f'[Voice message: "{transcript}"]'
        )
    services.context_cache[cache_key] = content
    return content


async def _audio_transcription_options(
    services: "AIUserServices", guild
) -> Tuple[str, str, int]:
    guild_conf = services.config.guild(guild)
    provider = (
        (await guild_conf.scan_audio_provider() or DEFAULT_STT_PROVIDER).strip().lower()
    )
    model = await guild_conf.scan_audio_model() or DEFAULT_STT_MODEL
    max_duration = int(
        await guild_conf.max_audio_duration() or DEFAULT_AUDIO_DURATION_LIMIT
    )
    return provider, model, max_duration


async def _trim_audio(audio: bytes, max_duration: int) -> Tuple[Optional[bytes], str]:
    if not shutil.which("ffmpeg"):
        return None, "ogg"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-t",
        str(max_duration),
        "-vn",
        "-acodec",
        "libopus",
        "-f",
        "ogg",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, stderr = await proc.communicate(audio)
    if proc.returncode != 0 or not output:
        logger.warning("ffmpeg failed to prepare audio for transcription: %s", stderr)
        return None, "ogg"
    return output, "ogg"
