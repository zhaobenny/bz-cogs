"""Triggers that force a response or identify conversation follow-ups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

import discord
from redbot.core import commands

from aiuser.config.constants import (
    GROK_MAX_WORDS,
    GROK_PRIMARY_TRIGGERS,
    GROK_SECONDARY_TRIGGERS,
)
from aiuser.core.validators import is_bot_mentioned_or_replied

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


async def get_conversation_reply_settings(
    services: "AIUserServices", ctx: commands.Context
) -> tuple[float, int]:
    """Get conversation reply settings based on member/role/channel/guild settings."""
    reply_percent = await services.resolver.resolve_for_ctx(
        "conversation_reply_percent", ctx
    )
    reply_time_seconds = await services.resolver.resolve_for_ctx(
        "conversation_reply_time", ctx
    )
    return reply_percent, reply_time_seconds


async def get_conversation_reply_chance(
    services: "AIUserServices", ctx: commands.Context
) -> Optional[float]:
    """Return the follow-up reply chance when this message is in conversation."""
    reply_percent, reply_time_seconds = await get_conversation_reply_settings(
        services, ctx
    )

    if reply_percent == 0 or reply_time_seconds == 0:
        return None

    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(seconds=reply_time_seconds)

    async for message in ctx.channel.history(limit=10):
        if (
            message.author.id == services.bot.user.id
            and len(message.embeds) == 0
            and message.created_at > cutoff_time
        ):
            return reply_percent

    return None


async def is_grok_triggered(services: "AIUserServices", ctx: commands.Context) -> bool:
    if not (await services.config.guild(ctx.guild).grok_trigger()):
        return False

    if len(ctx.message.content.split()) > GROK_MAX_WORDS:
        return False

    message_lower = ctx.message.content.lower()

    return any(word in message_lower for word in GROK_PRIMARY_TRIGGERS) and any(
        word in message_lower for word in GROK_SECONDARY_TRIGGERS
    )


async def is_always_reply_on_words_triggered(
    services: "AIUserServices", ctx: commands.Context
) -> bool:
    """Check if any always_reply_on_words appears in the message."""
    trigger_words = await services.resolver.resolve_for_ctx(
        "always_reply_on_words", ctx
    )
    if not trigger_words:
        return False

    message_lower = ctx.message.content.lower()
    return any(word.lower() in message_lower for word in trigger_words)


async def check_direct_triggers(
    services: "AIUserServices", ctx: commands.Context, message: discord.Message
) -> bool:
    trigger_funcs = [
        lambda: is_bot_mentioned_or_replied(services, message),
        lambda: is_always_reply_on_words_triggered(services, ctx),
        lambda: is_grok_triggered(services, ctx),
    ]

    # Short-circuit on first True
    for trigger_func in trigger_funcs:
        if await trigger_func():
            return True
    return False
