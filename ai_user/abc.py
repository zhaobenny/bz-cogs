from redbot.core import commands, Config
from redbot.core.bot import Red
from abc import ABC

# taken from here: https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/abc.py

class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass

class MixinMeta(ABC):
    def __init__(self, *args):
        self.bot : Red
        self.config : Config
        self.cached_options : dict
