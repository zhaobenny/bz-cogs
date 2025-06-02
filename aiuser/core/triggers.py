import random
from datetime import datetime, timedelta, timezone

from redbot.core import commands

from aiuser.config.constants import (
    GROK_MAX_WORDS,
    GROK_PRIMARY_TRIGGERS,
    GROK_SECONDARY_TRIGGERS,
)
from aiuser.types.abc import MixinMeta


async def is_in_conversation(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Check if bot should continue conversation based on recent messages"""
    reply_percent = await cog.config.guild(ctx.guild).conversation_reply_percent()
    reply_time_seconds = await cog.config.guild(ctx.guild).conversation_reply_time()

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

async def is_grok_triggered(cog: MixinMeta, ctx: commands.Context) -> bool:
    if not (await cog.config.guild(ctx.guild).grok_trigger()):
        return False

    if len(ctx.message.content.split()) > GROK_MAX_WORDS:
        return False

    message_lower = ctx.message.content.lower()
    
    return (any(word in message_lower for word in GROK_PRIMARY_TRIGGERS) and 
            any(word in message_lower for word in GROK_SECONDARY_TRIGGERS))