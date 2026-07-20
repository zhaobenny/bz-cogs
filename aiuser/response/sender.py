"""
Delivery of a finished pipeline result to the Discord channel.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Set

import discord
from discord.utils import MISSING
from redbot.core import commands

from aiuser.config.constants import REGEX_RUN_TIMEOUT
from aiuser.utils.utilities import to_thread

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices
    from aiuser.response.pipeline import PipelineResult

logger = logging.getLogger("red.bz_cogs.aiuser")

DISCORD_MESSAGE_LIMIT = 2000
REPLY_IF_OLDER_THAN_SECONDS = 8
RANDOM_REPLY_CHANCE = 0.25


async def deliver(
    services: "AIUserServices",
    ctx: commands.Context,
    result: "PipelineResult",
    can_reply: bool,
) -> Optional[discord.Message]:
  
    response = ""
    if result.completion:
        response = await _remove_patterns_from_response(
            ctx, services, result.completion
        )
    if not response and not result.files_to_send:
        return None

    files = result.files_to_send
    allowed = discord.AllowedMentions(
        everyone=False, roles=False, users=[ctx.message.author]
    )
    chunks = _chunk_message(response)
    last = len(chunks) - 1

    first_files = files if last == 0 else MISSING
    if can_reply and await _should_reply(ctx):
        try:
            sent_message = await ctx.message.reply(
                chunks[0],
                mention_author=False,
                allowed_mentions=allowed,
                files=first_files,
            )
        except discord.HTTPException:
            # trigger message got deleted; deliver without the reply link
            sent_message = await ctx.send(
                chunks[0], allowed_mentions=allowed, files=first_files
            )
    elif ctx.interaction:
        sent_message = await ctx.interaction.followup.send(
            chunks[0], allowed_mentions=allowed, files=first_files, wait=True
        )
    else:
        sent_message = await ctx.send(
            chunks[0], allowed_mentions=allowed, files=first_files
        )

    for idx, chunk in enumerate(chunks[1:], start=1):
        sent_message = await ctx.send(
            chunk, allowed_mentions=allowed, files=files if idx == last else MISSING
        )

    return sent_message


async def _should_reply(ctx: commands.Context) -> bool:
    if ctx.interaction:
        return False

    age_seconds = (
        datetime.now(timezone.utc) - ctx.message.created_at
    ).total_seconds()
    if age_seconds > REPLY_IF_OLDER_THAN_SECONDS:
        return True
    if random.random() < RANDOM_REPLY_CHANCE:
        return True

    # if the latest channel message is our own, reply to show which
    # message this answers
    async for last_msg in ctx.message.channel.history(limit=1):
        if last_msg.author == ctx.guild.me:
            return True
    return False


def _chunk_message(response: str) -> List[str]:
    if not response:
        return [""]

    chunks: List[str] = []
    remaining = response
    while len(remaining) > DISCORD_MESSAGE_LIMIT:
        cut = remaining.rfind("\n", 1, DISCORD_MESSAGE_LIMIT)
        if cut == -1:
            cut = remaining.rfind(" ", 1, DISCORD_MESSAGE_LIMIT)
        if cut == -1:
            cut = DISCORD_MESSAGE_LIMIT
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip(" \n")
    if remaining:
        chunks.append(remaining)
    return chunks


# --- cleanup ---


async def _remove_patterns_from_response(
    ctx: commands.Context, services: "AIUserServices", response: str
) -> str:
    """Strip text matching the guild's removelist regexes."""
    cleaned = response.strip(" \n")
    patterns = await services.config.guild(ctx.guild).removelist_regexes()
    if not patterns:
        return cleaned

    botname = ctx.guild.me.nick or ctx.guild.me.display_name
    patterns = [p.replace(r"{botname}", re.escape(botname)) for p in patterns]
    patterns = await _expand_authorname_patterns(ctx, patterns)

    for pattern in patterns:
        try:
            cleaned = await _compile_and_apply(pattern, cleaned)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout applying regex pattern: {pattern}")
        except Exception:
            logger.warning(f"Error applying regex pattern: {pattern}", exc_info=True)
    return cleaned


async def _expand_authorname_patterns(
    ctx: commands.Context, patterns: List[str]
) -> List[str]:
    """Turn each {authorname} pattern into one pattern per recent chatter.

    Author names come from a channel history fetch; only pay for it when
    some pattern actually uses them.
    """
    if not any("{authorname}" in pattern for pattern in patterns):
        return patterns

    authors: Set[str] = {
        msg.author.display_name
        async for msg in ctx.channel.history(limit=10)
        if msg.author != ctx.guild.me
    }

    expanded: List[str] = []
    for pattern in patterns:
        if "{authorname}" in pattern:
            expanded.extend(
                pattern.replace(r"{authorname}", re.escape(author))
                for author in authors
            )
        else:
            expanded.append(pattern)
    return expanded


@to_thread(timeout=REGEX_RUN_TIMEOUT)
def _compile_and_apply(pattern_str: str, text: str) -> str:
    pattern = re.compile(pattern_str)
    return pattern.sub("", text).strip(" \n")
