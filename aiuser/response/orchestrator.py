"""One response, end to end: build the conversation (unless the caller
already has one), run the LLM pipeline, deliver the result."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from redbot.core import commands

from aiuser.consent import maybe_send_consent_embed
from aiuser.context.assembler import ConversationAssembler
from aiuser.context.conversation import Conversation
from aiuser.providers.speech.transcripts import cache_audio_transcript
from aiuser.response.pipeline import LLMPipeline, PipelineError
from aiuser.response.sender import deliver
from aiuser.utils.cache import memory_cache_key, tool_calls_cache_key

if TYPE_CHECKING:
    import discord

    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")

_FAILURE_FEEDBACK: Dict[PipelineError, Tuple[str, str]] = {
    PipelineError.NO_PROVIDER: ("⚠️", "`aiuser` has no LLM backend available"),
    PipelineError.TIMED_OUT: ("💤", "`aiuser` request timed out"),
    PipelineError.RATE_LIMITED: ("💤", "`aiuser` request ratelimited"),
    PipelineError.REQUEST_FAILED: ("⚠️", "`aiuser` request failed"),
}


async def build_and_respond(
    services: "AIUserServices",
    ctx: commands.Context,
    history_anchor: Optional["discord.Message"] = None,
) -> None:
    assembler = ConversationAssembler(services, ctx, history_anchor=history_anchor)
    async with ctx.message.channel.typing():
        conversation = await assembler.build()

    # follow-ups the assembler discovered while reading channel history
    await maybe_send_consent_embed(
        services.consent, ctx.channel, assembler.undecided_users
    )
    if services.compaction_manager:
        await services.compaction_manager.check_and_run_compaction(
            ctx, assembler.compaction_candidates
        )

    await generate_and_send(services, ctx, conversation)


async def generate_and_send(
    services: "AIUserServices",
    ctx: commands.Context,
    conversation: Conversation,
    can_reply: bool = True,
) -> None:
    async with ctx.message.channel.typing():
        result = await LLMPipeline(services, ctx, conversation).run()
        if result.error is not None:
            await _notify_failure(ctx, result.error)
        sent_message = await deliver(services, ctx, result, can_reply)

    if sent_message is None:
        return

    transcripts = result.audio_transcripts_to_cache
    if sent_message.attachments and transcripts:
        cache_audio_transcript(services, sent_message.id, "\n".join(transcripts))

    # Preserve non-Discord entries for better context caching
    if result.tool_call_entries:
        key = tool_calls_cache_key(ctx.channel.id, sent_message.id)
        services.context_cache[key] = result.tool_call_entries
    if conversation.memory_entries:
        key = memory_cache_key(ctx.channel.id, ctx.message.id)
        services.context_cache[key] = conversation.memory_entries

    state = services.reply_channel_states[ctx.channel.id]
    state.last_bot_reply_at = sent_message.created_at
    if result.session_id:
        state.llm_session_id = result.session_id


async def _notify_failure(ctx: commands.Context, error: PipelineError) -> None:
    if error is PipelineError.NO_PROVIDER and ctx.interaction:
        await ctx.send(":warning: No LLM backend available.", ephemeral=True)
        return
    emoji, note = _FAILURE_FEEDBACK[error]
    await ctx.react_quietly(emoji, message=note)
