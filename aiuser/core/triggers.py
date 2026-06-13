"""Triggers that force a response regardless of the reply-percent roll."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from redbot.core import commands

from aiuser.config.constants import (
    GROK_MAX_WORDS,
    GROK_PRIMARY_TRIGGERS,
    GROK_SECONDARY_TRIGGERS,
)
from aiuser.core.validators import is_bot_mentioned_or_replied

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


async def is_in_conversation(
    services: "AIUserServices", ctx: commands.Context
) -> bool:
    """Check if bot should continue conversation based on recent messages"""
    reply_percent = await services.resolver.resolve_for_ctx(
        "conversation_reply_percent", ctx
    )
    reply_time_seconds = await services.resolver.resolve_for_ctx(
        "conversation_reply_time", ctx
    )

    if reply_percent == 0 or reply_time_seconds == 0:
        return False

    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(seconds=reply_time_seconds)

    async for message in ctx.channel.history(limit=10):
        if (
            message.author.id == services.bot.user.id
            and len(message.embeds) == 0
            and message.created_at > cutoff_time
        ):
            return random.random() < reply_percent

    return False


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
    """Check if any always_reply_on_words appears in the message"""
    trigger_words = await services.resolver.resolve_for_ctx(
        "always_reply_on_words", ctx
    )
    if not trigger_words:
        return False

    message_lower = ctx.message.content.lower()
    return any(word.lower() in message_lower for word in trigger_words)


async def check_triggers(
    services: "AIUserServices", ctx: commands.Context, message
) -> bool:
    trigger_funcs = [
        lambda: is_bot_mentioned_or_replied(services, message),
        lambda: is_always_reply_on_words_triggered(services, ctx),
        lambda: is_grok_triggered(services, ctx),
        lambda: is_in_conversation(services, ctx),
    ]

    # Short-circuit on first True
    for trigger_func in trigger_funcs:
        if await trigger_func():
            return True
    return False
