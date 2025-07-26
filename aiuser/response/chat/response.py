import asyncio
import logging
import random
import re
from datetime import datetime, timezone

from discord import AllowedMentions
from redbot.core import Config, commands

from aiuser.config.constants import REGEX_RUN_TIMEOUT
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.llm_pipeline import LLMPipeline
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import to_thread

logger = logging.getLogger("red.bz_cogs.aiuser")


# Use to_thread to compile & apply a regex pattern
@to_thread(timeout=REGEX_RUN_TIMEOUT)
def compile_and_apply(pattern_str: str, text: str) -> str:
    pattern = re.compile(pattern_str)
    return pattern.sub("", text).strip(" \n")


async def remove_patterns_from_response(
    ctx: commands.Context, config: Config, response: str
) -> str:
    # Get patterns from config and replace "{botname}".
    patterns = await config.guild(ctx.guild).removelist_regexes()
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    patterns = [p.replace(r"{botname}", botname) for p in patterns]

    # Expand patterns that have "{authorname}" based on recent authors.
    authors = {
        msg.author.display_name
        async for msg in ctx.channel.history(limit=10)
        if msg.author != ctx.guild.me
    }
    expanded_patterns = []
    for pattern in patterns:
        if "{authorname}" in pattern:
            for author in authors:
                expanded_patterns.append(pattern.replace(r"{authorname}", author))
        else:
            expanded_patterns.append(pattern)

    # Apply each pattern sequentially.
    cleaned = response.strip(" \n")
    for pattern in expanded_patterns:
        try:
            cleaned = await compile_and_apply(pattern, cleaned)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout applying regex pattern: {pattern}")
        except Exception:
            logger.warning(f"Error applying regex pattern: {pattern}", exc_info=True)
    return cleaned


async def should_reply(ctx: commands.Context) -> bool:
    if ctx.interaction:
        return False

    try:
        await ctx.fetch_message(ctx.message.id)
    except Exception:
        return False

    if (
        datetime.now(timezone.utc) - ctx.message.created_at
    ).total_seconds() > 8 or random.random() < 0.25:
        return True

    async for last_msg in ctx.message.channel.history(limit=1):
        if last_msg.author == ctx.message.guild.me:
            return True
    return False


async def send_response(ctx: commands.Context, response: str, can_reply: bool) -> bool:
    allowed = AllowedMentions(everyone=False, roles=False, users=[ctx.message.author])
    if len(response) >= 2000:
        for i in range(0, len(response), 2000):
            await ctx.send(response[i : i + 2000], allowed_mentions=allowed)
    elif can_reply and await should_reply(ctx):
        await ctx.message.reply(response, mention_author=False, allowed_mentions=allowed)
    elif ctx.interaction:
        await ctx.interaction.followup.send(response, allowed_mentions=allowed)
    else:
        await ctx.send(response, allowed_mentions=allowed)
    return True


async def create_chat_response(
    cog: MixinMeta, ctx: commands.Context, messages_list: MessagesList
) -> bool:
    pipeline = LLMPipeline(cog, ctx, messages=messages_list)
    response = await pipeline.run()
    if not response:
        return False

    cleaned_response = await remove_patterns_from_response(ctx, cog.config, response)
    if not cleaned_response:
        return False

    return await send_response(ctx, cleaned_response, messages_list.can_reply)
