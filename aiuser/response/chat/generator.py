
from redbot.core import Config, commands

from aiuser.types.abc import MixinMeta
from aiuser.messages_list.messages import MessagesList


class ChatGenerator():
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        self.ctx: commands.Context = ctx
        self.config: Config = cog.config
        self.bot = cog.bot
        self.msg_list = messages
        self.model = messages.model
        self.can_reply = messages.can_reply
        self.messages = messages.get_json()

    def generate_message(self):
        raise NotImplementedError
