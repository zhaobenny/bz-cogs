from dataclasses import asdict, dataclass, field
from discord import Message

from redbot.core.bot import Red

from redbot.core import Config

from ai_user.prompts.common.messages_item import MessagesItem



@dataclass()
class MessagesList:
    bot : Red
    config: Config
    messages: list = field(default_factory=list)
    messages_ids: list = field(default_factory=list)

    def add_msg(self, content : str, message : Message):
        if message.id in self.messages_ids:
            return
        role = "user" if message.author.id != self.bot.id else "assistant"
        messages_item = MessagesItem(role, content)
        self.messages.append(messages_item)
        self.messages_ids.append(message.id)

    def add_system(self, content : str):
        messages_item = MessagesItem("system", content)
        self.messages.append(messages_item)

    def get_messages(self):
        result = []
        for message in self.messages:
            result.append(asdict(message))
        return result