import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import List

import tiktoken
from discord import Message
from redbot.core import Config
from redbot.core.bot import Red

from ai_user.common.constants import OPENAI_MODEL_TOKEN_LIMIT
from ai_user.common.types import ContextOptions
from ai_user.prompts.common.helpers import (RoleType, format_embed_content,
                                            format_text_content,
                                            is_embed_valid)
from ai_user.prompts.common.messages_item import MessagesItem

logger = logging.getLogger("red.bz_cogs.ai_user")


@dataclass()
class MessagesList:
    bot: Red
    config: Config
    initial_message: Message
    messages: list = field(default_factory=list)
    messages_ids: set = field(default_factory=set)
    tokens: int = 0
    _encoding: tiktoken.Encoding = None
    model: str = None

    async def add_msg(self, content: str, message: Message, prepend: bool = False):
        if message.id in self.messages_ids:
            return

        role: RoleType = "user" if message.author.id != self.bot.id else "assistant"
        messages_item = MessagesItem(role, content)

        insertion_index = self._get_insertion_index(prepend)
        self.messages.insert(insertion_index, messages_item)
        self.messages_ids.add(message.id)
        await self._add_tokens(content)

    async def add_system(self, content: str, prepend: bool = False):
        messages_item = MessagesItem("system", content)
        insertion_index = self._get_insertion_index(prepend)
        self.messages.insert(insertion_index, messages_item)
        await self._add_tokens(content)

    async def _add_tokens(self, content):
        if not self._encoding:
            self.model = (await self.config.guild(self.initial_message.guild).model())
            self._encoding = tiktoken.encoding_for_model(self.model)
        tokens = self._encoding.encode(content, disallowed_special=())
        self.tokens += len(tokens)

    def _get_insertion_index(self, prepend: bool) -> int:
        return 0 if prepend else len(self.messages)

    def get_messages(self):
        result = []
        for message in self.messages:
            result.append(asdict(message))
        return result

    async def create_context(self, context_options: ContextOptions):
        limit = await self.config.guild(self.initial_message.guild).messages_backread()
        MAX_SECONDS_GAP = await self.config.guild(self.initial_message.guild).messages_backread_seconds()
        start_time: datetime = context_options.start_time + \
            timedelta(seconds=1) if context_options.start_time else None
        self.ignore_regex = context_options.ignore_regex
        self.cached_messages = context_options.cached_messages
        if not self.model:
            self.model = (await self.config.guild(self.initial_message.guild).model())

        past_messages = [message async for message in self.initial_message.channel.history(limit=limit,
                                                                                           before=self.initial_message,
                                                                                           after=start_time,
                                                                                           oldest_first=False)]

        if abs((past_messages[0].created_at - self.initial_message.created_at).total_seconds()) > MAX_SECONDS_GAP:
            return

        for i in range(len(past_messages)-1):
            if self.tokens > OPENAI_MODEL_TOKEN_LIMIT.get(self.model, 3000):
                return logger.warning(f"{self.tokens} tokens used - nearing limit, stopping context creation")
            if await self._valid_time_between_messages(past_messages, i, MAX_SECONDS_GAP):
                await self._add_contextual_message(past_messages[i])
            else:
                await self._add_contextual_message(past_messages[i])

    async def _valid_time_between_messages(self, past_messages: List[Message], index, max_gap) -> bool:
        time_between_messages = abs(past_messages[index].created_at - past_messages[index+1].created_at).total_seconds()
        if time_between_messages > max_gap:
            return False
        return True

    async def _add_contextual_message(self, message: Message):
        if self.ignore_regex and self.ignore_regex.search(message.content):
            return await self.add_system("Message skipped", prepend=True)

        if message.reference:
            # TODO: handle references
            pass

        print(self.cached_messages)

        if len(message.embeds) > 0 and is_embed_valid(message):
            return await self.add_msg(format_embed_content(message), message, prepend=True)
        elif message.content:
            return await self.add_msg(format_text_content(message), message, prepend=True)
        elif message.id in self.cached_messages:
            return await self.add_msg(self.cached_messages[message.id], message, prepend=True)
        else:
            return await self.add_system("Message skipped", prepend=True)
