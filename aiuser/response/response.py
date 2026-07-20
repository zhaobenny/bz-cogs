"""Orchestrates one full response: assemble context -> run LLM -> send."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from redbot.core import commands

from aiuser.context.assembler import ConversationAssembler
from aiuser.context.conversation import Conversation
from aiuser.speech.transcripts import cache_audio_transcript
from aiuser.response.pipeline import LLMPipeline
from aiuser.response.sender import remove_patterns_from_response, send_response

if TYPE_CHECKING:
    import discord

    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


async def create_response(
    services: "AIUserServices",
    ctx: commands.Context,
    conversation: Optional[Conversation] = None,
    history_anchor: Optional["discord.Message"] = None,
) -> bool:
    async with ctx.message.channel.typing():
        if conversation is None:
            conversation = await ConversationAssembler(
                services, ctx, history_anchor=history_anchor
            ).build()

        pipeline = LLMPipeline(services, ctx, conversation)
        response = await pipeline.run()

        if not response and not pipeline.files_to_send:
            return False

        cleaned_response = ""
        if response:
            cleaned_response = await remove_patterns_from_response(
                ctx, services.config, response
            )

        if not cleaned_response and not pipeline.files_to_send:
            return False

        sent_message = await send_response(
            ctx, cleaned_response, conversation.can_reply, files=pipeline.files_to_send
        )

        transcripts = pipeline.tool_context.audio_transcripts_to_cache
        if sent_message and sent_message.attachments and transcripts:
            cache_audio_transcript(services, sent_message.id, "\n".join(transcripts))

        # Preserve non-Discord entries for better context caching
        
        if sent_message and pipeline.tool_call_entries:
            cache_key = ("tool_calls", ctx.channel.id, sent_message.id)
            services.context_cache[cache_key] = pipeline.tool_call_entries
        if sent_message and conversation.memory_entries:
            cache_key = ("memory", ctx.channel.id, ctx.message.id)
            services.context_cache[cache_key] = conversation.memory_entries

        if sent_message:
            state = services.reply_channel_states[ctx.channel.id]
            state.last_bot_reply_at = sent_message.created_at
            if pipeline.session_id:
                state.llm_session_id = pipeline.session_id

        return sent_message is not None
