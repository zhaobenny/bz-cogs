
from redbot.core import Config, commands

from aiuser.messages_list.messages import MessagesList


class Chat_Generator():
    def __init__(self, ctx: commands.Context, config: Config, messages: MessagesList):
        self.ctx = ctx
        self.config = config
        self.msg_list = messages
        self.messages = messages.get_json()

    def generate_message(self):
        raise NotImplementedError
