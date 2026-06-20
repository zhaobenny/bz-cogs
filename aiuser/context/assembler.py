from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, List, Optional

import discord
from redbot.core import commands
from redbot.core.bot import Red

from aiuser.config.defaults import DEFAULT_PROMPT
from aiuser.config.model_info import get_model_info
from aiuser.consent import CONSENT_EMBED_TITLE
from aiuser.context.conversation import Conversation
from aiuser.context.converter.converter import MessageConverter
from aiuser.context.entry import (
    SYSTEM_NAME_MEMORY,
    SYSTEM_NAME_SUMMARY,
    MessageEntry,
)
from aiuser.context.memory.retriever import MemoryRetriever
from aiuser.utils.utilities import format_variables, mention_to_text

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.context")


class ConversationAssembler:
    """Builds the :class:`Conversation` for one triggering message.

    Payload order (oldest first):

        [summary] [history... (with cached tool calls)] [system prompt]
        [memory] [replied-to reference] [trigger message]

    History is walked newest-to-oldest and prepended, so it naturally stops
    when the token budget runs out and ends up in chronological order.
    """

    def __init__(
        self,
        services: "AIUserServices",
        ctx: commands.Context,
        history_anchor: Optional[discord.Message] = None,
    ):
        self.services = services
        self.config = services.config
        self.bot: Red = services.bot
        self.bot_id: int = self.bot.user.id
        self.ctx = ctx
        self.guild: discord.Guild = ctx.guild
        self.init_message: discord.Message = ctx.message
        self.history_anchor: discord.Message = history_anchor or ctx.message
        self.converter = MessageConverter(self.config, self.bot, ctx)
        self._optin_by_default = False

    async def build(
        self,
        *,
        prompt_override: Optional[str] = None,
        include_history: bool = True,
        include_trigger: bool = True,
    ) -> Conversation:
        guild_conf = self.config.guild(self.guild)

        model = await guild_conf.model()
        token_limit = (
            await guild_conf.custom_model_tokens_limit()
            or get_model_info(model).token_limit
        )
        if await self._should_use_image_model():
            model = await guild_conf.scan_images_model() or model

        conversation = Conversation(model=model, token_limit=token_limit)
        self._optin_by_default = await guild_conf.optin_by_default()

        prompt = prompt_override or await self._pick_prompt()
        await conversation.append_system(await format_variables(self.ctx, prompt))

        if include_history:
            memory = await self._fetch_relevant_memory()
            if memory:
                await conversation.append_system(memory, name=SYSTEM_NAME_MEMORY)

        if include_trigger:
            entries = await self._collect_message_entries(
                self.init_message, conversation
            )
            for entry in entries:
                await conversation.append(entry)

        if include_history:
            await self._prepend_history(conversation)

        return conversation

    # --- prompt / model selection ---

    async def _pick_prompt(self) -> str:
        """Select the prompt via member > role > channel > guild > global"""
        scoped_prompt = await self.services.resolver.resolve(
            "custom_text_prompt",
            guild=self.guild,
            channel=self.ctx.channel,
            member=self.init_message.author,
        )
        return scoped_prompt or await self.config.custom_text_prompt() or DEFAULT_PROMPT

    async def _should_use_image_model(self) -> bool:
        """Check if we should switch to the image scanning model"""
        if (
            self.ctx.interaction
            or not await self.config.guild(self.guild).scan_images()
        ):
            return False

        message = self.init_message

        if message.attachments and (
            message.attachments[0].content_type or ""
        ).startswith("image/"):
            return True

        if message.reference:
            ref = message.reference
            if not ref.channel_id or not ref.message_id:
                return False
            replied = ref.cached_message or await self.bot.get_channel(
                ref.channel_id
            ).fetch_message(ref.message_id)
            return bool(
                replied.attachments
                and (replied.attachments[0].content_type or "").startswith("image/")
            )

        return False

    # --- memory ---

    async def _fetch_relevant_memory(self) -> Optional[str]:
        if not await self.config.guild(self.guild).query_memories():
            return None
        if self.services.memories is None:
            return None
        retriever = MemoryRetriever(self.ctx, db=self.services.memories)
        return await retriever.fetch_relevant(mention_to_text(self.init_message))

    # --- message conversion / filtering ---

    async def _should_include(
        self, message: discord.Message, conversation: Conversation
    ) -> bool:
        if conversation.is_full():
            return False
        if message.id in conversation.seen_message_ids:
            logger.debug("Skipping duplicate message when creating context")
            return False

        ignore_regex = self.services.ignore_regex_cache.ignore_regex(self.guild.id)
        if ignore_regex and ignore_regex.search(message.content):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return False
        if message.author.id != self.bot_id and not self.services.consent.allows(
            message.author.id, optin_by_default=self._optin_by_default
        ):
            return False

        return True

    async def _collect_message_entries(
        self, message: discord.Message, conversation: Conversation
    ) -> List[MessageEntry]:
        """Entries for a message in payload order, reply-reference chain first."""
        if not await self._should_include(message, conversation):
            return []

        converted = await self.converter.convert(message) or []
        conversation.seen_message_ids.add(message.id)

        # the converter emits [special-content, message-text]; payload order is
        # message text first, then the attachment/embed description
        entries = list(reversed(converted))

        reference = message.reference
        if (
            reference
            and isinstance(reference.resolved, discord.Message)
            and message.author.id != self.bot_id
        ):
            referenced = await self._collect_message_entries(
                reference.resolved, conversation
            )
            entries = referenced + entries

        return entries

    # --- history ---

    async def _prepend_history(self, conversation: Conversation):
        guild_conf = self.config.guild(self.guild)
        limit = await guild_conf.messages_backread()
        max_seconds_gap = await guild_conf.messages_backread_seconds()

        start_time = self.services.override_prompt_start_time.get(self.guild.id)
        if start_time:
            start_time = start_time - timedelta(seconds=1)

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
            return

        if not self._within_gap(self.history_anchor, past_messages[0], max_seconds_gap):
            return

        if self.history_anchor.id != self.init_message.id:
            past_messages = [self.history_anchor] + past_messages

        undecided_users = await self.services.consent.get_undecided_users(
            self.guild, past_messages[:10]
        )

        # compaction: drop already-summarized messages, remember the summary
        summary = None
        compaction_candidates: List[discord.Message] = []
        compaction_enabled = False
        store = self.services.compaction_store
        if store and self.services.compaction_manager:
            compaction_enabled = await guild_conf.compaction_enabled()
            if compaction_enabled:
                compaction_candidates = await self._compaction_candidates(
                    past_messages, max_seconds_gap, conversation
                )
                last_compacted_id = await store.get_last_compacted_message_id(
                    self.guild.id, self.init_message.channel.id
                )
                if last_compacted_id:
                    past_messages = [
                        m for m in past_messages if m.id > last_compacted_id
                    ]
                summary = await store.get_summary(
                    self.guild.id, self.init_message.channel.id
                )

        # newest-to-oldest walk; the last fetched message only bounds the gap check
        for i in range(len(past_messages) - 1):
            if conversation.is_full():
                logger.debug(
                    f"{conversation.tokens} tokens used - nearing limit, "
                    f"stopping context creation for message {self.init_message.id}"
                )
                break

            message = past_messages[i]
            if self._is_consent_embed(message):
                continue

            within_gap = self._within_gap(
                message, past_messages[i + 1], max_seconds_gap
            )

            entries = await self._collect_message_entries(message, conversation)
            for entry in reversed(entries):
                await conversation.prepend(entry)

            if message.author.id == self.bot_id:
                await self._prepend_cached_tool_calls(conversation, message)

            if not within_gap:
                break

        if summary:
            await conversation.prepend_system(
                f"Summary of conversation before this point:\n{summary}",
                name=SYSTEM_NAME_SUMMARY,
            )

        if compaction_enabled and self.services.compaction_manager:
            await self.services.compaction_manager.check_and_run_compaction(
                self.ctx, compaction_candidates
            )

        await self.services.consent.maybe_send_consent_embed(
            self.init_message.channel, undecided_users
        )

    async def _compaction_candidates(
        self,
        past_messages: List[discord.Message],
        max_seconds_gap: int,
        conversation: Conversation,
    ) -> List[discord.Message]:
        """Messages that normal history processing is allowed to include."""
        candidates: List[discord.Message] = []
        for i in range(len(past_messages) - 1):
            message = past_messages[i]

            if not self._is_consent_embed(message):
                if await self._should_include(message, conversation):
                    candidates.append(message)

            if not self._within_gap(message, past_messages[i + 1], max_seconds_gap):
                break

        return candidates

    async def _prepend_cached_tool_calls(
        self, conversation: Conversation, bot_message: discord.Message
    ):
        """Re-inject cached tool call entries before an assistant response."""
        cache_key = (bot_message.channel.id, bot_message.id)
        cached_entries = self.services.tool_call_cache[cache_key]
        if not cached_entries:
            return

        for entry in reversed(cached_entries):
            await conversation.prepend(entry)

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
