from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

import discord
from openai import AsyncOpenAI
from redbot.core import Config, commands
from redbot.core.bot import Red

from aiuser.config.resolver import ScopedConfigResolver
from aiuser.consent import ConsentService
from aiuser.context.compaction import CompactionManager, CompactionStore
from aiuser.utils.cache import Cache
from aiuser.utils.vectorstore import VectorStore

if TYPE_CHECKING:
    from aiuser.core.reply_queue import ChannelReplyState

logger = logging.getLogger("red.bz_cogs.aiuser")


class GuildIgnoreRegexCache:
    """Compiled ignore regexes keyed by guild ID."""

    def __init__(self, config: Config):
        self._config = config
        self._ignore_regex: Dict[int, Optional[re.Pattern]] = {}

    async def load_all(self):
        """(Re)load compiled ignore regexes from config."""
        self._ignore_regex.clear()

        all_config = await self._config.all_guilds()
        for guild_id, guild_config in all_config.items():
            pattern = guild_config["ignore_regex"]
            try:
                self._ignore_regex[guild_id] = re.compile(pattern) if pattern else None
            except re.error:
                logger.warning(f"Invalid ignore regex configured for guild {guild_id}")
                self._ignore_regex[guild_id] = None

    def ignore_regex(self, guild_id: int) -> Optional[re.Pattern]:
        return self._ignore_regex.get(guild_id)

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
    ignore_regex_cache: GuildIgnoreRegexCache
    memories: Optional[VectorStore]
    compaction_store: Optional[CompactionStore]
    compaction_manager: Optional[CompactionManager]
    context_cache: Cache
    reply_channel_states: Dict[int, "ChannelReplyState"] = field(default_factory=dict)
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

        ignore_regex_cache = GuildIgnoreRegexCache(config)
        await ignore_regex_cache.load_all()

        services = cls(
            bot=bot,
            config=config,
            consent=consent,
            resolver=ScopedConfigResolver(config),
            ignore_regex_cache=ignore_regex_cache,
            memories=VectorStore(data_path),
            compaction_store=CompactionStore(data_path),
            compaction_manager=None,
            context_cache=Cache(limit=200),
            cog=cog,
        )
        services.compaction_manager = CompactionManager(services)
        return services
