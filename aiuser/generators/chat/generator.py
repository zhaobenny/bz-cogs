from aiuser.prompts.common.messagethread import MessageThread
from redbot.core import Config, commands

class Chat_Generator():
    def __init__(self, ctx: commands.Context, config: Config, thread: MessageThread):
        self.ctx = ctx
        self.config = config
        self.thread = thread

    def generate_message(self):
        raise NotImplementedError