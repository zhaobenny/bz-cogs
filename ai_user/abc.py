from datetime import datetime
from redbot.core import commands, Config
from redbot.core.bot import Red
from abc import ABC

from ai_user.common.cache import Cache
from ai_user.prompts.common.messages_item import MessagesItem

# taken from here: https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/abc.py


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass


class MixinMeta(ABC):
    def __init__(self, *args):
        self.bot: Red
        self.config: Config
        self.cached_options: dict
        self.override_prompt_start_time: dict[int, datetime]
        self.cached_messages: Cache[int, MessagesItem]
