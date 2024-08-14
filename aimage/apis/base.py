
from typing import Union

import discord
from redbot.core import commands

from aimage.abc import MixinMeta


class BaseAPI():
    def __init__(self, cog: MixinMeta, context: Union[commands.Context, discord.Interaction]):
        self.session = cog.session
        self.config = cog.config
        self.context = context
        self.guild = context.guild

    async def _init(self, *args, **kwargs):
        # for class variables that need to be async initialized
        raise NotImplementedError

    async def generate_image(self, *args, **kwargs):
        raise NotImplementedError

    async def generate_img2img(self, *args, **kwargs):
        raise NotImplementedError

    async def get_autocomplete(self, *args, **kwargs):
        raise NotImplementedError
