from abc import ABC

from aiohttp import ClientSession
from redbot.core import Config, commands
from redbot.core.bot import Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass


class MixinMeta(ABC):
    def __init__(self, *args):
        self.bot: Red
        self.config: Config
        self.session: ClientSession

    async def _get_endpoint(self, _):
        pass
