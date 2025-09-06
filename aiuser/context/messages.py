import json
import logging
from typing import List

import discord
from discord import Message
from redbot.core import commands
from redbot.core.data_manager import cog_data_path

from aiuser.context.consent.manager import ConsentManager
from aiuser.context.converter.converter import MessageConverter
from aiuser.context.entry import MessageEntry
from aiuser.context.history.builder import HistoryBuilder
from aiuser.context.memory.retriever import MemoryRetriever
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import encode_text_to_tokens

logger = logging.getLogger("red.bz_cogs.aiuser")

class MessagesThread:
    def __init__(
        self,
        cog: MixinMeta,
        ctx: commands.Context,
    ):
        self.bot = cog.bot
        self.config = cog.config
        self.ctx = ctx
        self.init_message = ctx.message
        self.guild = ctx.guild
        self.ignore_regex = cog.ignore_regex.get(self.guild.id, None)
        self.start_time = cog.override_prompt_start_time.get(
            self.guild.id)
        self.messages: List[MessageEntry] = []
        self.messages_ids = set()
        self.tokens = 0
        self.token_limit: int = None
        self.model: str = None
        self._encoding = None
        self.can_reply = True
        self.converter = MessageConverter(cog, ctx)
        self.consent_manager = ConsentManager(self.config, self.bot, self.guild)
        self.memory_retriever = MemoryRetriever(cog_data_path(cog), ctx)
        self.history_manager = HistoryBuilder(self)

    def __len__(self):
        return len(self.messages)

    def __repr__(self) -> str:
        return json.dumps(self.get_json(), indent=4)

    async def check_if_add(self, message: Message, allow_dupes: bool = False):
        if self.tokens > self.token_limit:
            return False

        if message.id in self.messages_ids and not allow_dupes:
            logger.debug(
                f"Skipping duplicate message in {message.guild.name} when creating context"
            )
            return False

        if self.ignore_regex and self.ignore_regex.search(message.content):
            return False
        if not await self.bot.allowed_by_whitelist_blacklist(message.author):
            return False
        if message.author.id in await self.config.optout():
            return False
        if not await self.consent_manager.is_user_allowed(message.author):
            return False

        return True

    async def add_msg(self, message: Message, index: int = None, force: bool = False):
        if not await self.check_if_add(message, force):
            return

        converted = await self.converter.convert(message)

        if not converted:
            return

        for entry in converted:
            if self.tokens > self.token_limit:
                return

            self.messages.insert(index or 0, entry)
            self.messages_ids.add(message.id)

            if isinstance(entry.content, list):
                for item in entry.content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        await self._add_tokens(item.get("text"))
                    elif item.get("type") == "image_url":
                        self.tokens += 255  # TODO: calculate actual image token cost
            else:
                await self._add_tokens(entry.content)

        # TODO: proper reply chaining
        if message.reference and isinstance(message.reference.resolved, discord.Message) and message.author.id != self.bot.user.id:
            await self.add_msg(message.reference.resolved, index=0)

    async def add_system(self, content: str, index: int = None):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("system", content)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_assistant(self, content: str = "", index: int = None, tool_calls: list = []):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("assistant", content, tool_calls=tool_calls)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_tool_result(self, content: str,  tool_call_id: int, index: int = None):
        if self.tokens > self.token_limit:
            return
        entry = MessageEntry("tool", content, tool_call_id=tool_call_id)
        self.messages.insert(index or 0, entry)
        await self._add_tokens(content)

    async def add_history(self):
        await self.insert_relevant_memory()
        await self.history_manager.add_history()

    async def insert_relevant_memory(self):
        relevant_memory = await self.memory_retriever.fetch_relevant(self.init_message.content)
        if relevant_memory:
            await self.add_system(relevant_memory, index=len(self.messages_ids))

    def get_json(self):
        return [
            {
                "role": message.role,
                "content": message.content,
                **({"tool_calls": message.tool_calls} if message.tool_calls else {}),
                **({"tool_call_id": message.tool_call_id} if hasattr(message, 'tool_call_id') and message.tool_call_id else {})
            }
            for message in self.messages
        ]

    async def _add_tokens(self, content):
        content = str(content)
        tokens = await encode_text_to_tokens(content)
        self.tokens += tokens
