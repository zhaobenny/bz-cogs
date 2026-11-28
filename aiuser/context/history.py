from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import discord

from aiuser.consent import CONSENT_EMBED_TITLE

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.context")


@dataclass(frozen=True)
class HistoryWindow:
    messages: list[discord.Message]
    recent_messages: list[discord.Message]
    summary: str | None = None


def is_consent_embed(message: discord.Message, bot_id: int) -> bool:
    return bool(
        message.author.id == bot_id
        and message.embeds
        and message.embeds[0].title == CONSENT_EMBED_TITLE
    )


def within_gap(
    message: discord.Message, next_message: discord.Message, max_seconds_gap: int
) -> bool:
    seconds_diff = abs(message.created_at - next_message.created_at).total_seconds()
    return seconds_diff <= max_seconds_gap


async def should_include_message(
    services: AIUserServices,
    guild_id: int,
    message: discord.Message,
    *,
    optin_by_default: bool,
    seen_ids: set[int] | None = None,
) -> bool:
    bot_id = services.bot.user.id
    if is_consent_embed(message, bot_id):
        return False
    if seen_ids is not None and message.id in seen_ids:
        logger.debug("Skipping duplicate message when creating context")
        return False

    ignore_regex = services.ignore_regex_cache.ignore_regex(guild_id)
    if ignore_regex and ignore_regex.search(message.content):
        return False
    if not await services.bot.allowed_by_whitelist_blacklist(message.author):
        return False
    return not (
        message.author.id != bot_id
        and not services.consent.allows(
            message.author.id, optin_by_default=optin_by_default
        )
    )


async def drop_compacted_messages(
    services: AIUserServices,
    guild: discord.Guild,
    channel_id: int,
    window: list[discord.Message],
) -> tuple[list[discord.Message], str | None]:
    store = services.compaction_store
    manager = services.compaction_manager
    if not store or not manager:
        return window, None
    if not await services.config.guild(guild).compaction_enabled():
        return window, None

    last_compacted_id = await store.get_last_compacted_message_id(guild.id, channel_id)
    if last_compacted_id:
        window = [m for m in window if m.id > last_compacted_id]
    summary = await store.get_summary(guild.id, channel_id)
    return window, summary


async def select_history_window(
    services: AIUserServices,
    guild: discord.Guild,
    init_message: discord.Message,
    *,
    history_anchor: discord.Message | None = None,
    max_messages: int | None = None,
) -> HistoryWindow:
    """Pick the gap-bounded window of past messages, oldest first."""
    guild_conf = services.config.guild(guild)
    limit = await guild_conf.messages_backread()
    if max_messages is not None:
        limit = min(limit, max_messages)
    if limit <= 0:
        return HistoryWindow(messages=[], recent_messages=[], summary=None)

    max_seconds_gap = await guild_conf.messages_backread_seconds()
    anchor = history_anchor or init_message
    start_time = services.override_prompt_start_time.get(guild.id)
    if start_time:
        start_time = start_time - timedelta(seconds=1)

    recent_messages = [
        message
        async for message in anchor.channel.history(
            limit=limit,
            before=anchor,
            after=start_time,
            oldest_first=False,
        )
    ]
    if not recent_messages or not within_gap(
        anchor, recent_messages[0], max_seconds_gap
    ):
        return HistoryWindow(messages=[], recent_messages=[], summary=None)

    if anchor.id != init_message.id:
        recent_messages = [anchor] + recent_messages

    window: list[discord.Message] = []
    previous = anchor
    for message in recent_messages:
        if not within_gap(previous, message, max_seconds_gap):
            break
        window.append(message)
        previous = message

    window.reverse()
    filtered, summary = await drop_compacted_messages(
        services, guild, init_message.channel.id, window
    )
    return HistoryWindow(
        messages=filtered, recent_messages=recent_messages, summary=summary
    )
