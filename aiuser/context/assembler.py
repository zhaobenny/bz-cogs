from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from redbot.core import commands

from aiuser.config.model_info import get_model_info
from aiuser.context.conversation import Conversation
from aiuser.context.converter.converter import MessageConverter
from aiuser.context.entry import MessageEntry
from aiuser.context.history import (
    select_history_window,
    should_include_message,
)
from aiuser.context.relevant_memory import fetch_relevant_memory
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
        services: AIUserServices,
        ctx: commands.Context,
        history_anchor: discord.Message | None = None,
    ):
        self.services = services
        self.bot_id: int = self.services.bot.user.id
        self.ctx = ctx
        self.guild: discord.Guild = ctx.guild
        self.init_message: discord.Message = ctx.message
        self.history_anchor: discord.Message = history_anchor or ctx.message
        self.converter = MessageConverter(services, ctx)
        self._optin_by_default = False
        self._seen_ids: set[int] = set()
        self.undecided_users: set[discord.Member] = set()
        self.compaction_candidates: list[discord.Message] = []

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

        history = await select_history_window(
            self.services,
            self.guild,
            self.init_message,
            history_anchor=self.history_anchor,
        )
        if history.recent_messages:
            self.undecided_users = await self.services.consent.get_undecided_users(
                self.guild, history.recent_messages[:10]
            )
        if history.summary:
            await conversation.append_system(
                f"Summary of conversation before this point:\n{history.summary}",
                protected=True,
            )
        for message in history.messages:
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
        model = await guild_conf.model() or await self.services.config.default_model()
        token_limit = (
            await guild_conf.custom_model_tokens_limit()
            or get_model_info(model).token_limit
        )
        return Conversation(model=model, token_limit=token_limit)

    # --- memory ---

    async def _fetch_relevant_memory(self) -> str | None:
        if not await self.services.config.guild(self.guild).query_memories():
            return None
        return await fetch_relevant_memory(
            self.ctx, self.services.memories, mention_to_text(self.init_message)
        )

    # --- message conversion / filtering ---

    async def _convert_message(
        self, message: discord.Message
    ) -> list[MessageEntry] | None:
        if not await should_include_message(
            self.services,
            self.guild.id,
            message,
            optin_by_default=self._optin_by_default,
            seen_ids=self._seen_ids,
        ):
            return None

        self._seen_ids.add(message.id)
        return await self.converter.convert(message) or []

    async def _append_message(
        self, conversation: Conversation, message: discord.Message
    ):
        """Append message: its hidden entries (cached tool calls
        for the bot's messages, cached retrieved memory for users'), then its
        visible entries."""
        entries = await self._convert_message(message)
        if not entries:
            return
        self.compaction_candidates.append(message)

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
