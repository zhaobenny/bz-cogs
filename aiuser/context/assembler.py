from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Set

import discord
from redbot.core import commands

from aiuser.config.model_info import get_model_info
from aiuser.consent import CONSENT_EMBED_TITLE
from aiuser.context.conversation import Conversation
from aiuser.context.converter.converter import MessageConverter
from aiuser.context.entry import MessageEntry
from aiuser.context.memory import fetch_relevant_memory
from aiuser.utils.cache import memory_cache_key, tool_calls_cache_key
from aiuser.utils.utilities import format_variables, mention_to_text

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.context")


class ConversationAssembler:
    """Builds the :class:`Conversation` for one triggering message.

    Payload order (oldest first):

        [summary] [history... (with cached tool calls)] [system prompt]
        [memory] [replied-to reference] [trigger message]

    """

    def __init__(
        self,
        services: "AIUserServices",
        ctx: commands.Context,
        history_anchor: Optional[discord.Message] = None,
    ):
        self.services = services
        self.bot_id: int = self.services.bot.user.id
        self.ctx = ctx
        self.guild: discord.Guild = ctx.guild
        self.init_message: discord.Message = ctx.message
        self.history_anchor: discord.Message = history_anchor or ctx.message
        self.converter = MessageConverter(services, ctx)
        self._optin_by_default = False
        self._seen_ids: Set[int] = set()
        self.summary: Optional[str] = None
        self.undecided_users: Set[discord.Member] = set()
        self.compaction_candidates: List[discord.Message] = []

    async def build(self) -> Conversation:
        guild_conf = self.services.config.guild(self.guild)
        self._optin_by_default = await guild_conf.optin_by_default()
        conversation = await self._new_conversation()
        conversation.from_message_context = True

        prompt = await self.services.resolver.resolve_prompt(
            guild=self.guild,
            channel=self.ctx.channel,
            member=self.init_message.author,
        )
        formatted_prompt = await format_variables(self.ctx, prompt, self.services)

        window = await self._select_history_window()

        if self.summary:
            await conversation.append_system(
                f"Summary of conversation before this point:\n{self.summary}",
                protected=True,
            )
        for message in window:
            await self._append_message(conversation, message)
        await conversation.append_system(formatted_prompt, protected=True)
        if memory := await self._fetch_relevant_memory():
            entry = await conversation.append_system(memory)
            conversation.memory_entries.append(entry)

        reference = self.init_message.reference
        if reference and isinstance(reference.resolved, discord.Message):
            for entry in await self._convert_message(reference.resolved) or []:
                await conversation.append(entry)
        for entry in await self._convert_message(self.init_message) or []:
            await conversation.append(entry)

        await self._switch_to_image_model(conversation)
        await conversation.prune_oldest_if_over_limit()
        return conversation

    async def build_prompt_only(self, prompt: str) -> Conversation:
        """System prompt only"""
        conversation = await self._new_conversation()
        await conversation.append_system(
            await format_variables(self.ctx, prompt, self.services),
            protected=True,
        )
        return conversation

    async def _new_conversation(self) -> Conversation:
        guild_conf = self.services.config.guild(self.guild)
        model = await guild_conf.model()
        token_limit = (
            await guild_conf.custom_model_tokens_limit()
            or get_model_info(model).token_limit
        )
        return Conversation(model=model, token_limit=token_limit)

    # --- memory ---

    async def _fetch_relevant_memory(self) -> Optional[str]:
        if not await self.services.config.guild(self.guild).query_memories():
            return None
        return await fetch_relevant_memory(
            self.ctx, self.services.memories, mention_to_text(self.init_message)
        )

    # --- message conversion / filtering ---

    async def _should_include(self, message: discord.Message) -> bool:
        if self._is_consent_embed(message):
            return False
        if message.id in self._seen_ids:
            logger.debug("Skipping duplicate message when creating context")
            return False

        ignore_regex = self.services.ignore_regex_cache.ignore_regex(self.guild.id)
        if ignore_regex and ignore_regex.search(message.content):
            return False
        if not await self.services.bot.allowed_by_whitelist_blacklist(message.author):
            return False
        if message.author.id != self.bot_id and not self.services.consent.allows(
            message.author.id, optin_by_default=self._optin_by_default
        ):
            return False

        return True

    async def _convert_message(
        self, message: discord.Message
    ) -> Optional[List[MessageEntry]]:
        if not await self._should_include(message):
            return None

        self._seen_ids.add(message.id)
        return await self.converter.convert(message) or []

    async def _select_history_window(self) -> List[discord.Message]:
        """Pick the gap-bounded window of past messages, oldest first."""
        guild_conf = self.services.config.guild(self.guild)
        limit = await guild_conf.messages_backread()
        max_seconds_gap = await guild_conf.messages_backread_seconds()

        start_time = self.services.override_prompt_start_time.get(self.guild.id)

        # fetch one extra message: the last one only bounds the gap walk
        past_messages = [
            message
            async for message in self.history_anchor.channel.history(
                limit=limit + 1,
                before=self.history_anchor,
                after=start_time,
                oldest_first=False,
            )
        ]
        if not past_messages:
            return []
        if not self._within_gap(self.history_anchor, past_messages[0], max_seconds_gap):
            return []
        if self.history_anchor.id != self.init_message.id:
            past_messages = [self.history_anchor] + past_messages

        self.undecided_users = await self.services.consent.get_undecided_users(
            self.guild, past_messages[:10]
        )

        window: List[discord.Message] = []
        for message, older_message in zip(past_messages, past_messages[1:]):
            window.append(message)
            if not self._within_gap(message, older_message, max_seconds_gap):
                break
        window.reverse()

        return await self._drop_compacted(window)

    async def _drop_compacted(
        self, window: List[discord.Message]
    ) -> List[discord.Message]:
        store = self.services.compaction_store
        manager = self.services.compaction_manager
        if not store or not manager:
            return window
        if not await self.services.config.guild(self.guild).compaction_enabled():
            return window

        self.compaction_candidates = [
            m for m in window if await self._should_include(m)
        ]
        last_compacted_id = await store.get_last_compacted_message_id(
            self.guild.id, self.init_message.channel.id
        )
        if last_compacted_id:
            window = [m for m in window if m.id > last_compacted_id]
        self.summary = await store.get_summary(
            self.guild.id, self.init_message.channel.id
        )
        return window

    async def _append_message(
        self, conversation: Conversation, message: discord.Message
    ):
        """Append message: its hidden entries (cached tool calls
        for the bot's messages, cached retrieved memory for users'), then its
        visible entries."""
        entries = await self._convert_message(message)
        if not entries:
            return

        if message.author.id == self.bot_id:
            cache_key = tool_calls_cache_key(message.channel.id, message.id)
        else:
            cache_key = memory_cache_key(message.channel.id, message.id)
        for entry in self.services.context_cache[cache_key] or []:
            await conversation.append(entry)

        for entry in entries:
            await conversation.append(entry)

    # --- misc ---

    async def _switch_to_image_model(self, conversation: Conversation):
        """Swap to the image-scanning model when any entry carries an image."""
        has_images = False
        for entry in conversation.entries:
            if not isinstance(entry.content, list):
                continue
            if any(
                isinstance(item, dict) and item.get("type") == "image_url"
                for item in entry.content
            ):
                has_images = True
                break
        if not has_images:
            return

        guild_conf = self.services.config.guild(self.guild)
        image_model = await guild_conf.scan_images_model() or conversation.model
        conversation.model = image_model
        conversation.token_limit = (
            await guild_conf.custom_model_tokens_limit()
            or get_model_info(image_model).token_limit
        )

    def _is_consent_embed(self, message: discord.Message) -> bool:
        return (
            message.author.id == self.bot_id
            and message.embeds
            and message.embeds[0].title == CONSENT_EMBED_TITLE
        )

    @staticmethod
    def _within_gap(
        message: discord.Message, next_message: discord.Message, max_seconds_gap: int
    ) -> bool:
        seconds_diff = abs(message.created_at - next_message.created_at).total_seconds()
        return seconds_diff <= max_seconds_gap
