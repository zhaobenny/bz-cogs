from dataclasses import asdict, dataclass, field
from typing import List

from discord import Message
from redbot.core import Config
from redbot.core.bot import Red
from ai_user.prompts.common.helpers import RoleType, format_embed_content, format_text_content, is_embed_valid

from ai_user.prompts.common.messages_item import MessagesItem


@dataclass()
class MessagesList:
    bot: Red
    config: Config
    messages: list = field(default_factory=list)
    messages_ids: set = field(default_factory=set)

    def add_msg(self, content: str, message: Message, prepend : bool = False):
        if message.id in self.messages_ids:
            return

        role : RoleType = "user" if message.author.id != self.bot.id else "assistant"
        messages_item = MessagesItem(role, content)

        insertion_index = self._get_insertion_index(prepend)
        self.messages.insert(insertion_index, messages_item)

        self.messages_ids.add(message.id)

    def add_system(self, content: str, prepend : bool = False):
        messages_item = MessagesItem("system", content)
        insertion_index = self._get_insertion_index(prepend)
        self.messages.insert(insertion_index, messages_item)

    def _get_insertion_index(self, prepend: bool) -> int:
        return 0 if prepend else len(self.messages)

    def get_messages(self):
        result = []
        for message in self.messages:
            result.append(asdict(message))
        return result

    async def create_context(self, initial_message: Message, start_time):
        limit = await self.config.guild(initial_message.guild).messages_backread()
        max_seconds_limit = await self.config.guild(initial_message.guild).messages_backread_seconds()

        past_messages = [message async for message in initial_message.channel.history(limit=limit,
                                                                                 before=initial_message,
                                                                                 after=start_time,
                                                                                 oldest_first=False)]

        if abs((past_messages[0].created_at - initial_message.created_at).total_seconds()) > max_seconds_limit:
            return

        for i in range(len(past_messages)-1):
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

    async def _add_contextual_message(self, message : Message):
        if message.reference:
            # TODO: handle reference
            pass

        if len(message.embeds) > 0 and is_embed_valid(message):
            self.add_msg(format_embed_content(message), message, prepend=True)
        elif message.content:
            self.add_msg(format_text_content(message), message, prepend=True)
        else:
            self.add_system("Message skipped")



