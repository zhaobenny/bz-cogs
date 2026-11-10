from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from enum import Enum, auto

import discord
from redbot.core import Config
from redbot.core.bot import Red

logger = logging.getLogger("red.bz_cogs.aiuser")


class ConsentDecision(Enum):
    UNDECIDED = auto()
    OPTED_IN = auto()
    OPTED_OUT = auto()


class ConsentService:
    """The single owner of bot-wide opt-in/opt-out state.

    All reads go through in-memory decisions (loaded at cog load), all writes
    are serialized behind a lock and persisted to config, so concurrent
    button presses / commands / dashboard submissions cannot drop each other's
    changes. Every consumer (commands, consent buttons, dashboard, message
    filtering, GDPR deletion) must go through this service.
    """

    def __init__(self, bot: Red, config: Config):
        self.bot: Red = bot
        self.config = config
        self._lock = asyncio.Lock()
        self._decisions: dict[int, ConsentDecision] = {}

    async def load(self):
        async with self._lock:
            opted_in = await self.config.optin()
            opted_out = await self.config.optout()
            self._decisions = {
                user_id: ConsentDecision.OPTED_IN for user_id in opted_in
            }
            # Opt-out takes precedence.
            self._decisions.update(
                {user_id: ConsentDecision.OPTED_OUT for user_id in opted_out}
            )

    def decision(self, user_id: int) -> ConsentDecision:
        return self._decisions.get(user_id, ConsentDecision.UNDECIDED)

    def is_opted_in(self, user_id: int) -> bool:
        return self.decision(user_id) is ConsentDecision.OPTED_IN

    def is_opted_out(self, user_id: int) -> bool:
        return self.decision(user_id) is ConsentDecision.OPTED_OUT

    def has_decided(self, user_id: int) -> bool:
        return self.decision(user_id) is not ConsentDecision.UNDECIDED

    def allows(self, user_id: int, *, optin_by_default: bool) -> bool:
        decision = self.decision(user_id)
        if decision is ConsentDecision.OPTED_OUT:
            return False
        if decision is ConsentDecision.OPTED_IN:
            return True
        return optin_by_default

    async def opt_in(self, user_id: int) -> bool:
        async with self._lock:
            if self.decision(user_id) is ConsentDecision.OPTED_IN:
                return False
            self._decisions[user_id] = ConsentDecision.OPTED_IN
            await self._persist()
            return True

    async def opt_out(self, user_id: int) -> bool:
        async with self._lock:
            if self.decision(user_id) is ConsentDecision.OPTED_OUT:
                return False
            self._decisions[user_id] = ConsentDecision.OPTED_OUT
            await self._persist()
            return True

    async def remove_user_data(self, user_id: int):
        async with self._lock:
            if self._decisions.pop(user_id, None) is not None:
                await self._persist()

    async def _persist(self):
        await self.config.optin.set(
            [
                user_id
                for user_id, decision in self._decisions.items()
                if decision is ConsentDecision.OPTED_IN
            ]
        )
        await self.config.optout.set(
            [
                user_id
                for user_id, decision in self._decisions.items()
                if decision is ConsentDecision.OPTED_OUT
            ]
        )

    # --- queries for the consent embed (sending lives in consent.view) ---

    async def get_undecided_users(
        self, guild: discord.Guild, messages: Iterable[discord.Message]
    ) -> set[discord.Member]:
        """Authors in `messages` who have not made an opt-in/out choice yet."""
        if await self.config.guild(guild).optin_by_default():
            return set()

        return {
            message.author
            for message in messages
            if not message.author.bot and not self.has_decided(message.author.id)
        }
