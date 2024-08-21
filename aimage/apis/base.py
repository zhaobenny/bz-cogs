
from typing import Union

import discord
from redbot.core import commands

from aimage.abc import MixinMeta
from aimage.apis.response import ImageResponse


class BaseAPI():
    def __init__(self, cog: MixinMeta, context: Union[commands.Context, discord.Interaction]):
        self.session = cog.session
        self.config = cog.config
        self.context = context
        self.guild = context.guild

    async def _init(self, *args, **kwargs):
        # for class variables that need to be await initialized
        raise NotImplementedError

    async def generate_image(self, *args, **kwargs) -> ImageResponse:
        raise NotImplementedError

    async def generate_img2img(self, *args, **kwargs) -> ImageResponse:
        # skip if not supported
        raise NotImplementedError

    async def update_autocomplete_cache(self, cache: dict):
        # skip if not supported
        raise NotImplementedError
