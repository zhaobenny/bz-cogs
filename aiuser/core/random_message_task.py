"""Background task that occasionally sends unprompted messages."""

from __future__ import annotations

import datetime
import logging
import random
from typing import TYPE_CHECKING, List, Tuple

import discord
from discord.ext import tasks
from redbot.core import commands

from aiuser.config.constants import RANDOM_MESSAGE_TASK_RETRY_SECONDS
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

    def start(self):
        self._random_message_loop.start()

    def cancel(self):
        self._random_message_loop.cancel()

    @tasks.loop(seconds=RANDOM_MESSAGE_TASK_RETRY_SECONDS)
    async def _random_message_loop(self):
        if await get_llm_provider(self.services) is None:
            return
        if not self.services.bot.is_ready():
            return

        all_config = await self.services.config.all_guilds()
        for guild_id, guild_config in all_config.items():
            # Each guild is processed independently; a failure or skip in one
            # guild must not starve the others.
            try:
                await self._maybe_send_random_message(
                    guild_id, guild_config["channels_whitelist"]
                )
            except Exception:
                logger.exception(
                    f"Failed random message processing for guild {guild_id}, continuing"
                )

    async def _maybe_send_random_message(self, guild_id: int, channels: List[int]):
        try:
            last, ctx = await self._get_discord_context(guild_id, channels)
        except Exception:
            return

        guild = last.guild
        channel = last.channel

        if not await self._check_if_valid_for_random_message(guild, last):
            return

        topics = (
            await self.services.config.guild(guild).random_messages_prompts() or None
        )
        if not topics:
            logger.warning(
                f"No random message topics were found in {guild.name}, skipping"
            )
            return

        prompt = await self.services.resolver.resolve_prompt(
            guild=guild, channel=channel
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

    async def _get_discord_context(
        self, guild_id: int, channels: List[int]
    ) -> Tuple[discord.Message, commands.Context]:
        guild = self.services.bot.get_guild(guild_id)

        if not channels:
            raise ValueError(f"Channels are empty in guild {guild.name}")

        channel = guild.get_channel(random.choice(channels))

        if not channel:
            raise ValueError(f"Channel not found in guild {guild.name}")

        last_message = await channel.fetch_message(channel.last_message_id)
        ctx = await self.services.bot.get_context(last_message)
        ctx.author = ensure_member_like(ctx.author)

        return last_message, ctx

    async def _check_if_valid_for_random_message(
        self, guild: discord.Guild, last: discord.Message
    ) -> bool:
        if await self.services.bot.cog_disabled_in_guild(self.services.cog, guild):
            return False

        try:
            if not (await self.services.bot.ignored_channel_or_guild(last)):
                return False
        except Exception:
            return False

        if not await self.services.config.guild(guild).random_messages_enabled():
            return False
        if (
            random.random()
            > await self.services.config.guild(guild).random_messages_percent()
        ):
            return False

        if last.author.id == guild.me.id:
            # skip spamming channel with random event messages
            return False

        last_created = last.created_at.replace(tzinfo=datetime.timezone.utc)

        seconds_since_last = abs(
            (
                datetime.datetime.now(datetime.timezone.utc) - last_created
            ).total_seconds()
        )
        if seconds_since_last < 3600:
            # only sent to channels with 1 hour since last message
            return False

        return True
