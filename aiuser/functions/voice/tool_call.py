import io
import logging
import re
from typing import Any, Dict, Optional

import discord

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.functions.voice.native import send_voice_message
from aiuser.providers.speech.constants import MAX_VOICE_WORDS
from aiuser.providers.speech.transcripts import cache_audio_transcript
from aiuser.providers.speech.tts import PROVIDERS, voice_settings

logger = logging.getLogger("red.bz_cogs.aiuser.tools")

CUSTOM_EMOJI_RE = re.compile(r"<a?:[A-Za-z0-9_]{2,32}:\d{17,20}>?")


def _audio_file_extension(audio: bytes) -> str:
    if audio.startswith(b"RIFF") and audio[8:12] == b"WAVE":
        return "wav"
    return "mp3"


class VoiceRequestToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.VOICE_REQUEST,
            description=(
                "Use this to send a voice message instead of a text reply. Use it "
                "when voice would make the conversation more engaging, such as "
                "when something is funny or annoying. If asked to say, speak, or "
                "read something out loud, use voice when it is 3 sentences or "
                "shorter."
            ),
            parameters=Parameters(
                properties={
                    "text": {
                        "type": "string",
                        "description": (
                            "The text to turn into spoken audio. Tone modifiers "
                            "can be placed in brackets, such as [pause], [happy], "
                            "[angry], [sad], [soft], [excited], [laughing], "
                            "[whispering], [screaming], [sobbing], [moaning], "
                            "[sighing], or [clear throat]. If using [singing], "
                            "repeat it for every verse or half-verse."
                        ),
                    },
                },
                required=["text"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        text = str(arguments.get("text") or "").strip()
        if not text:
            return "No text was provided for voice generation."

        settings = await voice_settings(
            tool_context.services.config, tool_context.ctx.guild
        )
        voice_provider = PROVIDERS.get(settings.provider)
        if voice_provider is None:
            return f"Voice provider `{settings.provider}` is not available."

        voice_text = CUSTOM_EMOJI_RE.sub(".", text)
        voice_text = " ".join(voice_text.split())

        word_count = len(voice_text.split())
        if word_count > MAX_VOICE_WORDS:
            return (
                f"Voice generation is limited to {MAX_VOICE_WORDS} words. "
                f"The provided text has {word_count} words."
            )

        try:
            audio = await voice_provider(
                tool_context.services.bot,
                tool_context.services.config,
                voice_text,
                settings.model,
                settings.voice,
            )
        except ValueError as e:
            return str(e)
        except Exception:
            logger.exception("Failed to generate voice audio")
            return "Couldn't generate voice audio."

        try:
            sent = await send_voice_message(tool_context.ctx, audio)
            if sent:
                att = next(iter(sent.get("attachments") or []), None)
                if att:
                    cache_audio_transcript(
                        tool_context.services, int(sent["id"]), voice_text
                    )
                return "The requested voice message was generated and sent."
        except Exception:
            logger.debug(
                "Native Discord voice message send failed; falling back to audio file",
                exc_info=True,
            )

        filename = f"{tool_context.ctx.me.display_name} speaking.{_audio_file_extension(audio)}"
        tool_context.attach_file(discord.File(io.BytesIO(audio), filename=filename))
        tool_context.audio_transcripts_to_cache.append(voice_text)
        return "The requested voice audio was generated and sent."
