from dataclasses import InitVar, dataclass, field
from typing import Literal, Optional

from discord import Member, Message

RoleType = Literal['user', 'assistant']

@dataclass()
class MessagesItem:
    message : InitVar[Message]
    bot : InitVar[Member]
    role: Optional[RoleType] = field(init=False)
    content: Optional[str] = field(init=False)
    id: Optional[int] = field(init=False)

    def __post_init__(self, message: Message, bot):
        self.id = message.id
        self.role = "user" if message.author != bot else "assistant"
        message_content = self._format_message_content(message)
        self.content = f'User "{message.author.name}" said: {message_content}' if self.role == "user" else message_content

    def _asdict(self):
        """ Custom asdict method to exclude id from the dict """
        exclude = ('id',)
        return {k: v for k, v in self.__dict__.items() if k not in exclude}

    @staticmethod
    def _format_message_content(message: Message) -> str:
        content = message.content
        mentions = message.mentions + message.role_mentions + message.channel_mentions

        if not mentions:
            return content

        for mentioned in mentions:
            mention = mentioned.mention.replace("!", "")
            if mentioned in message.channel_mentions:
                content = content.replace(mention, f'#{mentioned.name}')
            else:
                content = content.replace(mention, f'@{mentioned.name}')

        return content