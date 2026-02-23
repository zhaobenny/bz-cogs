from typing import Optional

import discord
from redbot.core import commands

from aiuser.settings.scope import get_settings_target_scope
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions
from aiuser.settings.utilities import truncate_prompt
from aiuser.types.types import COMPATIBLE_MENTIONS


class ImageRequestFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="imagerequest")
    async def imagerequest(self, ctx: commands.Context):
        """Image generation function settings (per server)"""
        pass

    @imagerequest.command(name="toggle")
    async def imagerequest_toggle(self, ctx: commands.Context):
        """Toggle the image request function on or off"""
        from aiuser.functions.imagerequest.tool_call import ImageRequestToolCall

        await self.toggle_function_group(
            ctx, [ImageRequestToolCall.function_name], "Image Request"
        )

    @imagerequest.command(name="endpoint")
    async def imagerequest_endpoint(
        self, ctx: commands.Context, *, endpoint: str = None
    ):
        """Set a custom image generation endpoint

        If not set, the cog will attempt to use the currently set OpenAI endpoint to generate images.
        """
        await self.config.guild(ctx.guild).function_calling_image_custom_endpoint.set(
            endpoint or None
        )
        e = discord.Embed(
            title="Image request endpoint set to:",
            description=f"{endpoint or 'Autodetected'}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=e)

    @imagerequest.command(name="model")
    async def imagerequest_model(self, ctx: commands.Context, *, model: str = None):
        """Set the image generation model to use for supported endpoints.

        If not set, the cog will attempt to use reasonable defaults based on the endpoint.
        """
        await self.config.guild(ctx.guild).function_calling_image_model.set(
            model or None
        )
        desc = f"{model}" if model else "Default"
        e = discord.Embed(
            title="Image request model set to:",
            description=desc,
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=e)

    @imagerequest.command(name="preprompt")
    async def imagerequest_preprompt(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS],
        *,
        preprompt: Optional[str] = None,
    ):
        """Set or clear a preprompt that is prepended to image generation prompts.

        If multiple preprompts can be used, the most specific preprompt will be used, eg. it will go for: member > role > channel > server

        **Arguments**
            - `mention` *(Optional)* A specific user, role, or channel. If not provided, sets for the server.
            - `preprompt` *(Optional)* The preprompt to set. If blank, will remove current preprompt.
        """
        PREPROMPT_LIMIT = 3200
        if preprompt and len(preprompt) > PREPROMPT_LIMIT:
            return await ctx.send(
                f"Preprompt too long ({len(preprompt)}/{PREPROMPT_LIMIT}). Please shorten it to under {PREPROMPT_LIMIT} characters."
            )

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)

        if not config_attr:
            return await ctx.send(":warning: Invalid mention type provided.")

        if not preprompt:
            await config_attr.function_calling_image_preprompt.set(None)
            return await ctx.send(
                f"The preprompt for this {mention_type.name.lower()} will no longer use a custom preprompt."
            )

        await config_attr.function_calling_image_preprompt.set(preprompt)
        e = discord.Embed(
            title=f"Image request preprompt set for {mention_type.name.lower()}:",
            description=truncate_prompt(preprompt),
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=e)
