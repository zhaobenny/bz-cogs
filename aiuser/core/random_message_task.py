"""Background task that occasionally sends unprompted messages."""

from __future__ import annotations

import datetime
import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import tasks

from aiuser.config.constants import RANDOM_MESSAGE_TASK_RETRY_SECONDS
from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.context.assembler import ConversationAssembler
from aiuser.llm.registry import get_llm_provider
from aiuser.response.response import create_response
from aiuser.utils.adapters import ensure_member_like
from aiuser.utils.utilities import format_variables

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


class RandomMessageTask:
    """Owned by the cog (constructed in cog_load, cancelled in cog_unload)."""

    def __init__(self, services: "AIUserServices"):
        self.services = services
        self.config = services.config
        self.bot = services.bot

    def start(self):
        self._random_message_loop.start()

    def cancel(self):
        self._random_message_loop.cancel()

    @tasks.loop(seconds=RANDOM_MESSAGE_TASK_RETRY_SECONDS)
    async def _random_message_loop(self):
        if await get_llm_provider(self.services) is None:
            return
        if not self.bot.is_ready():
            return

        whitelists = self.services.guild_cache.all_channels_whitelists()
        for guild_id, channels in whitelists.items():
            # Each guild is processed independently; a failure or skip in one
            # guild must not starve the others.
            try:
                await self._maybe_send_random_message(guild_id, channels)
            except Exception:
                logger.exception(
                    f"Failed random message processing for guild {guild_id}, continuing"
                )

    async def _maybe_send_random_message(self, guild_id: int, channels: list):
        try:
            last, ctx = await self._get_discord_context(guild_id, channels)
        except Exception:
            return

        guild = last.guild
        channel = last.channel

        if not await self._check_if_valid_for_random_message(guild, last):
            return

        topics = await self.config.guild(guild).random_messages_prompts() or None
        if not topics:
            logger.warning(
                f"No random message topics were found in {guild.name}, skipping"
            )
            return

        scoped_prompt = await self.services.resolver.resolve(
            "custom_text_prompt", guild=guild, channel=channel
        )
        prompt = (
            scoped_prompt or await self.config.custom_text_prompt() or DEFAULT_PROMPT
        )

        conversation = await ConversationAssembler(self.services, ctx).build(
            prompt_override=prompt, include_history=False, include_trigger=False
        )
        topic = await format_variables(ctx, random.choice(topics))
        await conversation.append_system(
            f"Using the persona above, follow these instructions: {topic}"
        )
        conversation.can_reply = False

        logger.debug(f"Sending random message to #{channel.name} at {guild.name}")
        await create_response(self.services, ctx, conversation)

    async def _get_discord_context(self, guild_id: int, channels: list):
        guild = self.bot.get_guild(guild_id)

        if not channels:
            raise ValueError(f"Channels are empty in guild {guild.name}")

        channel = guild.get_channel(random.choice(channels))

        if not channel:
            raise ValueError(f"Channel not found in guild {guild.name}")

        last_message = await channel.fetch_message(channel.last_message_id)
        ctx = await self.bot.get_context(last_message)
        ctx.author = ensure_member_like(ctx.author)

        return last_message, ctx

    async def _check_if_valid_for_random_message(
        self, guild: discord.Guild, last: discord.Message
    ) -> bool:
        if await self.bot.cog_disabled_in_guild(self.services.cog, guild):
            return False

        try:
            if not (await self.bot.ignored_channel_or_guild(last)):
                return False
        except Exception:
            return False

        if not await self.config.guild(guild).random_messages_enabled():
            return False
        if random.random() > await self.config.guild(guild).random_messages_percent():
            return False

        if last.author.id == guild.me.id:
            # skip spamming channel with random event messages
            return False

        last_created = last.created_at.replace(tzinfo=datetime.timezone.utc)

        seconds_since_last = abs(
            (datetime.datetime.now(datetime.timezone.utc) - last_created).total_seconds()
        )
        if seconds_since_last < 3600:
            # only sent to channels with 1 hour since last message
            return False

        return True
