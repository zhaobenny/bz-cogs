from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Set

import discord
from redbot.core import Config
from redbot.core.bot import Red

logger = logging.getLogger("red.bz_cogs.aiuser")


class ConsentService:
    """The single owner of bot-wide opt-in/opt-out state.

    All reads go through in-memory sets (loaded once at cog load), all writes
    are serialized behind a lock and persisted to config, so concurrent
    button presses / commands / dashboard submissions cannot drop each other's
    changes. Every consumer (commands, consent buttons, dashboard, message
    filtering, GDPR deletion) must go through this service.
    """

    def __init__(self, bot: Red, config: Config):
        self.bot: Red = bot
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
        """GDPR deletion: drop any stored consent decision for the user."""
        async with self._lock:
            changed = user_id in self._optin or user_id in self._optout
            self._optin.discard(user_id)
            self._optout.discard(user_id)
            if changed:
                await self._persist()

    async def _persist(self):
        await self.config.optin.set(list(self._optin))
        await self.config.optout.set(list(self._optout))

    # --- queries for the consent embed (sending lives in consent.view) ---

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
