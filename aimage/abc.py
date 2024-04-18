from abc import ABC

import discord
from aiohttp import ClientSession
from redbot.core import Config, commands
from redbot.core.bot import Red


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    pass


class MixinMeta(ABC):
    bot: Red
    config: Config
    session: ClientSession
    generating: dict
    autocomplete_cache: dict

    def __init__(self, *args):
        pass

    async def _get_endpoint(self, guild: discord.Guild):
        """ Gets the correct endpoint for the guild """
        pass

    async def _fetch_data(self, guild: discord.Guild, endpoint_suffix: str):
        """ Helper function to fetch data from Stable Diffusion endpoint """
        pass

    async def get_auth(self, auth_str: str):
        pass

    async def generate_image(self, *args, **kwargs):
        pass

    async def generate_img2img(self, *args, **kwargs):
        pass
