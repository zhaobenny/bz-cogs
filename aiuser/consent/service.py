from __future__ import annotations

import asyncio
import logging
import random
from typing import Iterable, Set

import discord
from redbot.core import Config

logger = logging.getLogger("red.bz_cogs.aiuser")

CONSENT_EMBED_TITLE = ":information_source: AI User Opt-In / Opt-Out"


class ConsentService:
    """The single owner of bot-wide opt-in/opt-out state.

    All reads go through in-memory sets (loaded once at cog load), all writes
    are serialized behind a lock and persisted to config, so concurrent
    button presses / commands / dashboard submissions cannot drop each other's
    changes. Every consumer (commands, consent buttons, dashboard, message
    filtering, GDPR deletion) must go through this service.
    """

    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self._lock = asyncio.Lock()
        self._optin: Set[int] = set()
        self._optout: Set[int] = set()

    async def load(self):
        self._optin = set(await self.config.optin())
        self._optout = set(await self.config.optout())

    # --- queries (sync, hot path) ---

    def is_opted_in(self, user_id: int) -> bool:
        return user_id in self._optin

    def is_opted_out(self, user_id: int) -> bool:
        return user_id in self._optout

    def has_decided(self, user_id: int) -> bool:
        return user_id in self._optin or user_id in self._optout

    def allows(self, user_id: int, *, optin_by_default: bool) -> bool:
        """Whether a user's messages may be processed."""
        if user_id in self._optout:
            return False
        if user_id in self._optin:
            return True
        return optin_by_default

    # --- mutations ---

    async def opt_in(self, user_id: int) -> bool:
        """Opt a user in. Returns False if they already were."""
        async with self._lock:
            if user_id in self._optin:
                return False
            self._optin.add(user_id)
            self._optout.discard(user_id)
            await self._persist()
            return True

    async def opt_out(self, user_id: int) -> bool:
        """Opt a user out. Returns False if they already were."""
        async with self._lock:
            if user_id in self._optout:
                return False
            self._optout.add(user_id)
            self._optin.discard(user_id)
            await self._persist()
            return True

    async def remove_user_data(self, user_id: int):
        """GDPR deletion: drop the user's opt-in record.

        The opt-out record is deliberately kept, so a deletion request never
        silently re-enables processing of the user's messages.
        """
        async with self._lock:
            if user_id in self._optin:
                self._optin.discard(user_id)
                await self._persist()

    async def _persist(self):
        await self.config.optin.set(list(self._optin))
        await self.config.optout.set(list(self._optout))

    # --- consent embed ---

    async def get_undecided_users(
        self, guild: discord.Guild, messages: Iterable[discord.Message]
    ) -> Set[discord.Member]:
        """Authors in `messages` who have not made an opt-in/out choice yet."""
        if await self.config.guild(guild).optin_by_default():
            return set()

        return {
            message.author
            for message in messages
            if not message.author.bot and not self.has_decided(message.author.id)
        }

    async def maybe_send_consent_embed(
        self, channel: discord.abc.Messageable, users: Set[discord.Member]
    ) -> bool:
        """Send the opt-in/out embed if warranted. Returns True when sent."""
        if not users:
            return False
        if await self.config.guild(channel.guild).optin_disable_embed():
            return False
        # 33% chance, or always when several users still need to decide
        if not (random.random() <= 0.33 or len(users) > 3):
            return False

        from aiuser.consent.view import ConsentView

        users_mentions = ", ".join(user.mention for user in users)
        embed = discord.Embed(
            title=CONSENT_EMBED_TITLE,
            color=await self.bot.get_embed_color(channel),
        )
        embed.description = (
            f"{users_mentions}\n"
            "Please choose whether to allow a subset of your Discord messages from any server with the bot, "
            "to be sent to OpenAI or an external party.\n"
            "This will allow the bot to reply to your messages or use your messages.\n"
            "This message will disappear if all current chatters have made a choice."
        )
        await channel.send(embed=embed, view=ConsentView(self))
        return True
