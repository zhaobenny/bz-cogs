"""Shared cache of audio transcripts, keyed by Discord message ID.

Written by the STT converter and the voice tool (for TTS it just sent), read
back when building conversation context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

AUDIO_TRANSCRIPT_CACHE_NAMESPACE = "audio_transcript"


def cache_audio_transcript(
    services: "AIUserServices", message_id: int, transcript: str
) -> None:
    services.context_cache[(AUDIO_TRANSCRIPT_CACHE_NAMESPACE, message_id)] = (
        f'[Voice message: "{transcript}"]'
    )


def cached_audio_transcript(
    services: "AIUserServices", message_id: int
) -> Optional[str]:
    return services.context_cache[(AUDIO_TRANSCRIPT_CACHE_NAMESPACE, message_id)]
