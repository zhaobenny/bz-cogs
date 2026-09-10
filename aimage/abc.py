from __future__ import annotations

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

    async def generate_image(self, *args, **kwargs):
        pass

    async def generate_img2img(self, *args, **kwargs):
        pass

    async def get_api_instance(self, ctx: commands.Context | discord.Interaction):
        pass

    async def _update_autocomplete_cache(
        self,
        ctx: commands.Context | discord.Interaction,
    ):
        pass
