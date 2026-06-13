from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import discord
from openai import AsyncOpenAI
from redbot.core import Config, commands
from redbot.core.bot import Red

from aiuser.config.resolver import ScopedConfigResolver
from aiuser.consent import ConsentService
from aiuser.context.compaction import CompactionManager
from aiuser.utils.cache import Cache
from aiuser.utils.compaction.store import CompactionStore
from aiuser.utils.vectorstore import VectorStore

logger = logging.getLogger("red.bz_cogs.aiuser")


class GuildSettingsCache:
    """Write-through cache for the per-guild options read on every message.

    These are the only config values cached outside Red's Config (the regex
    needs compiling; the others are on the hot path of every message event).
    All writers must go through the setters here so the cache and config can
    never disagree.
    """

    def __init__(self, config: Config):
        self._config = config
        self._optin_by_default: Dict[int, bool] = {}
        self._channels_whitelist: Dict[int, List[int]] = {}
        self._ignore_regex: Dict[int, Optional[re.Pattern]] = {}

    async def load_all(self):
        """(Re)load every guild's cached options from config."""
        self._optin_by_default.clear()
        self._channels_whitelist.clear()
        self._ignore_regex.clear()

        all_config = await self._config.all_guilds()
        for guild_id, guild_config in all_config.items():
            self._optin_by_default[guild_id] = guild_config["optin_by_default"]
            self._channels_whitelist[guild_id] = guild_config["channels_whitelist"]
            pattern = guild_config["ignore_regex"]
            try:
                self._ignore_regex[guild_id] = re.compile(pattern) if pattern else None
            except re.error:
                logger.warning(f"Invalid ignore regex configured for guild {guild_id}")
                self._ignore_regex[guild_id] = None

    # --- reads (hot path, sync) ---

    def optin_by_default(self, guild_id: int) -> bool:
        return self._optin_by_default.get(guild_id, False)

    def channels_whitelist(self, guild_id: int) -> List[int]:
        return self._channels_whitelist.get(guild_id, [])

    def all_channels_whitelists(self) -> Dict[int, List[int]]:
        return dict(self._channels_whitelist)

    def ignore_regex(self, guild_id: int) -> Optional[re.Pattern]:
        return self._ignore_regex.get(guild_id)

    # --- writes (config + cache together) ---

    async def set_optin_by_default(self, guild: discord.Guild, value: bool):
        await self._config.guild(guild).optin_by_default.set(value)
        self._optin_by_default[guild.id] = value

    async def set_channels_whitelist(
        self, guild: discord.Guild, channel_ids: List[int]
    ):
        await self._config.guild(guild).channels_whitelist.set(channel_ids)
        self._channels_whitelist[guild.id] = channel_ids

    async def set_ignore_regex(self, guild: discord.Guild, pattern: Optional[str]):
        """Set (and compile) the ignore regex. Raises ``re.error`` if invalid."""
        compiled = re.compile(pattern) if pattern else None
        await self._config.guild(guild).ignore_regex.set(pattern)
        self._ignore_regex[guild.id] = compiled


@dataclass
class AIUserServices:
    """Everything the cog wires together at load time.

    This is the one place to look to see what the cog depends on. Functions
    take this (or just the pieces they need) instead of the cog instance.
    """

    bot: Red
    config: Config
    consent: ConsentService
    resolver: ScopedConfigResolver
    guild_cache: GuildSettingsCache
    memories: Optional[VectorStore]
    compaction_store: Optional[CompactionStore]
    compaction_manager: Optional[CompactionManager]
    tool_call_cache: Cache
    override_prompt_start_time: Dict[int, datetime] = field(default_factory=dict)
    openai_client: Optional[AsyncOpenAI] = None
    # only for Red APIs that require the cog instance (eg. cog_disabled_in_guild)
    cog: Optional[commands.Cog] = None

    @classmethod
    async def create(
        cls, bot: Red, config: Config, data_path: Path, cog: commands.Cog
    ) -> "AIUserServices":
        consent = ConsentService(bot, config)
        await consent.load()

        guild_cache = GuildSettingsCache(config)
        await guild_cache.load_all()

        services = cls(
            bot=bot,
            config=config,
            consent=consent,
            resolver=ScopedConfigResolver(config),
            guild_cache=guild_cache,
            memories=VectorStore(data_path),
            compaction_store=CompactionStore(data_path),
            compaction_manager=None,
            tool_call_cache=Cache(limit=100),
            cog=cog,
        )
        services.compaction_manager = CompactionManager(services)
        return services
