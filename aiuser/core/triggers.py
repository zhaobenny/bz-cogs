import random
from datetime import datetime, timedelta, timezone

from redbot.core import commands

from aiuser.config.constants import (
    GROK_MAX_WORDS,
    GROK_PRIMARY_TRIGGERS,
    GROK_SECONDARY_TRIGGERS,
)
from aiuser.core.hierarchy import get_ctx_hierarchical_config_value
from aiuser.core.validators import is_bot_mentioned_or_replied
from aiuser.types.abc import MixinMeta


async def is_in_conversation(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Check if bot should continue conversation based on recent messages"""
    reply_percent, reply_time_seconds = await get_conversation_reply_settings(cog, ctx)

    if reply_percent == 0 or reply_time_seconds == 0:
        return False

    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(seconds=reply_time_seconds)

    async for message in ctx.channel.history(limit=10):
        if (
            message.author.id == cog.bot.user.id
            and len(message.embeds) == 0
            and message.created_at > cutoff_time
        ):
            return random.random() < reply_percent

    return False


async def get_conversation_reply_settings(
    cog: MixinMeta, ctx: commands.Context
) -> tuple[float, int]:
    """Get conversation reply settings based on member/role/channel/guild settings"""
    reply_percent = await get_ctx_hierarchical_config_value(
        cog, ctx, "conversation_reply_percent"
    )
    reply_time_seconds = await get_ctx_hierarchical_config_value(
        cog, ctx, "conversation_reply_time"
    )
    return reply_percent, reply_time_seconds


async def is_grok_triggered(cog: MixinMeta, ctx: commands.Context) -> bool:
    if not (await cog.config.guild(ctx.guild).grok_trigger()):
        return False

    if len(ctx.message.content.split()) > GROK_MAX_WORDS:
        return False

    message_lower = ctx.message.content.lower()

    return any(word in message_lower for word in GROK_PRIMARY_TRIGGERS) and any(
        word in message_lower for word in GROK_SECONDARY_TRIGGERS
    )


async def is_always_reply_on_words_triggered(
    cog: MixinMeta, ctx: commands.Context
) -> bool:
    """Check if any always_reply_on_words appears in the message"""
    trigger_words = await get_ctx_hierarchical_config_value(
        cog, ctx, "always_reply_on_words"
    )
    if not trigger_words:
        return False

    message_lower = ctx.message.content.lower()
    return any(word.lower() in message_lower for word in trigger_words)


async def check_triggers(cog: MixinMeta, ctx: commands.Context, message) -> bool:
    trigger_funcs = [
        lambda: is_bot_mentioned_or_replied(cog, message),
        lambda: is_always_reply_on_words_triggered(cog, ctx),
        lambda: is_grok_triggered(cog, ctx),
        lambda: is_in_conversation(cog, ctx),
    ]

    # Short-circuit on first True
    for trigger_func in trigger_funcs:
        if await trigger_func():
            return True
    return False
