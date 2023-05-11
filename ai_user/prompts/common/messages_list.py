import logging
from dataclasses import asdict, dataclass, field
from typing import List

import tiktoken
from discord import Message
from redbot.core import Config
from redbot.core.bot import Red

from ai_user.constants import OPENAI_MODEL_TOKEN_LIMIT
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
            model = (await self.config.guild(self.initial_message.guild).model())
            self._encoding = tiktoken.encoding_for_model(model)
        tokens = self._encoding.encode(content, disallowed_special=())
        self.tokens += len(tokens)

    def _get_insertion_index(self, prepend: bool) -> int:
        return 0 if prepend else len(self.messages)

    def get_messages(self):
        result = []
        for message in self.messages:
            result.append(asdict(message))
        return result

    async def create_context(self, start_time=None):
        limit = await self.config.guild(self.initial_message.guild).messages_backread()
        max_seconds_limit = await self.config.guild(self.initial_message.guild).messages_backread_seconds()
        model = await self.config.guild(self.initial_message.guild).model()

        past_messages = [message async for message in self.initial_message.channel.history(limit=limit,
                                                                                           before=self.initial_message,
                                                                                           after=start_time,
                                                                                           oldest_first=False)]

        if abs((past_messages[0].created_at - self.initial_message.created_at).total_seconds()) > max_seconds_limit:
            return

        for i in range(len(past_messages)-1):
            if self.tokens > OPENAI_MODEL_TOKEN_LIMIT.get(model, 3000):
                logger.warning(f"{self.tokens} tokens used - nearing limit, stopping context creation")
                return
            if await self._valid_time_between_messages(past_messages, i, max_seconds_limit):
                await self._add_contextual_message(past_messages[i])
            else:
                await self._add_contextual_message(past_messages[i])
                return

    async def _valid_time_between_messages(self, past_messages: List[Message], index, max_seconds_limit) -> bool:
        time_between_messages = abs(past_messages[index].created_at - past_messages[index+1].created_at).total_seconds()
        if time_between_messages > max_seconds_limit:
            return False
        return True

    async def _add_contextual_message(self, message: Message):
        if message.reference:
            # TODO: handle reference
            pass

        if len(message.embeds) > 0 and is_embed_valid(message):
            await self.add_msg(format_embed_content(message), message, prepend=True)
        elif message.content:
            await self.add_msg(format_text_content(message), message, prepend=True)
        else:
            # TODO: handle attachments
            await self.add_system("Message skipped", prepend=True)
