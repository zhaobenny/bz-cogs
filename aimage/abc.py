from abc import ABC

from aiohttp import ClientSession
import discord
from redbot.core import Config, commands
from redbot.core.bot import Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass


class MixinMeta(ABC):
    def __init__(self, *args):
        self.bot: Red
        self.config: Config
        self.session: ClientSession

    async def _get_endpoint(self, guild: discord.Guild):
        pass

    async def _fetch_data(self, guild: discord.Guild, endpoint_suffix: str):
        pass

    async def generate_image(self, *args, **kwargs):
        pass
