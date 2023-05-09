from dataclasses import asdict, dataclass, field
from redbot.core import Config

from ai_user.prompts.common.messages_item import MessagesItem
from ai_user.prompts.common.messages_system_item import MessagesSystemItem


@dataclass()
class MessagesList:
    messages: list = field(default_factory=list)
    ids: list = field(default_factory=list)
    config: Config = field(default_factory=Config)

    async def add_user_msg(self, message, cached={}):
        if message.id in self.ids:
            return
        if message.id in cached.keys():
            self.messages.append(self.cached_msgs[message.id])
        else:
            item = MessagesItem(message, self.bot)._asdict()
            if await self.is_non_text_content(message):
                cached[message.id] = item
            self.messages.append(item)

    async def is_non_text_content(self, message):
        if message.attachments and await self.config.guild(message.guild).scan_images():
            return True
        if len(message.embeds) == 0 or not message.embeds[0].title or not message.embeds[0].description:
            return True
        return False

    def add_system_msg(self, content: str):
        self.messages.append(asdict(MessagesSystemItem(content)))

    def is_id_in_messages(self, id: int) -> bool:
        return id in self.ids
