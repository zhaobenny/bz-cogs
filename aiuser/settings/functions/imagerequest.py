from typing import Optional

import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.settings.scope import (
    get_effective_scoped_setting_for_target,
    get_settings_target_scope,
)
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions
from aiuser.settings.utilities import add_prompt_metrics_fields, truncate_prompt
from aiuser.types.types import COMPATIBLE_MENTIONS


class ImageRequestFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="image", aliases=["imagerequest"])
    async def imagerequest(self, ctx: commands.Context):
        """Image generation function settings (per server)"""
        pass

    @imagerequest.command(name="show")
    async def imagerequest_show(self, ctx: commands.Context):
        """Show image generation tool settings"""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools = await guild_conf.function_calling_functions()
        endpoint = await guild_conf.function_calling_image_custom_endpoint()
        model = await guild_conf.function_calling_image_model()
        embed = discord.Embed(
            title="Image tool settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled",
            value="Yes" if names.IMAGE_REQUEST in enabled_tools else "No",
        )
        embed.add_field(name="Endpoint", value=f"`{endpoint or 'Autodetected'}`")
        embed.add_field(name="Model", value=f"`{model or 'Default'}`")
        return await ctx.send(embed=embed)

    @imagerequest.command(name="enable")
    async def imagerequest_enable(self, ctx: commands.Context):
        """Enable the image generation tool"""
        await self.set_function_group(ctx, [names.IMAGE_REQUEST], "Image", True)

    @imagerequest.command(name="disable")
    async def imagerequest_disable(self, ctx: commands.Context):
        """Disable the image generation tool"""
        await self.set_function_group(ctx, [names.IMAGE_REQUEST], "Image", False)

    @imagerequest.group(name="endpoint", invoke_without_command=True)
    async def imagerequest_endpoint(self, ctx: commands.Context):
        """Show the image generation endpoint"""
        endpoint = await self.config.guild(
            ctx.guild
        ).function_calling_image_custom_endpoint()
        return await ctx.maybe_send_embed(
            f"Image endpoint: `{endpoint or 'Autodetected'}`"
        )

    @imagerequest_endpoint.command(name="set")
    async def imagerequest_endpoint_set(self, ctx: commands.Context, *, endpoint: str):
        """Set a custom image generation endpoint"""
        await self.config.guild(ctx.guild).function_calling_image_custom_endpoint.set(
            endpoint
        )
        return await ctx.send(f"Image endpoint set to `{endpoint}`.")

    @imagerequest_endpoint.command(name="clear")
    async def imagerequest_endpoint_clear(self, ctx: commands.Context):
        """Use the currently configured OpenAI endpoint for image generation"""
        await self.config.guild(ctx.guild).function_calling_image_custom_endpoint.set(
            None
        )
        return await ctx.send("Image endpoint reset to autodetection.")

    @imagerequest.group(name="model", invoke_without_command=True)
    async def imagerequest_model(self, ctx: commands.Context):
        """Show the image generation model"""
        model = await self.config.guild(ctx.guild).function_calling_image_model()
        return await ctx.maybe_send_embed(f"Image model: `{model or 'Default'}`")

    @imagerequest_model.command(name="set")
    async def imagerequest_model_set(self, ctx: commands.Context, *, model: str):
        """Set the image generation model"""
        await self.config.guild(ctx.guild).function_calling_image_model.set(model)
        return await ctx.send(f"Image model set to `{model}`.")

    @imagerequest_model.command(name="clear")
    async def imagerequest_model_clear(self, ctx: commands.Context):
        """Use the default image generation model"""
        await self.config.guild(ctx.guild).function_calling_image_model.set(None)
        return await ctx.send("Image model reset to the provider default.")

    @imagerequest.group(name="preprompt", invoke_without_command=True)
    async def imagerequest_preprompt(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Show the effective image preprompt for the server or a target"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        preprompt = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "function_calling_image_preprompt"
        )
        embed = discord.Embed(
            title=f"Image preprompt on this {mention_type.name.lower()}:",
            description=truncate_prompt(preprompt) if preprompt else "None",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagerequest_preprompt.command(name="set")
    async def imagerequest_preprompt_set(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
        *,
        preprompt: str,
    ):
        """Set an image preprompt for the server or a target"""
        PREPROMPT_LIMIT = 3200
        if len(preprompt) > PREPROMPT_LIMIT:
            return await ctx.send(
                f"Preprompt too long ({len(preprompt)}/{PREPROMPT_LIMIT}). Please shorten it to under {PREPROMPT_LIMIT} characters."
            )

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.function_calling_image_preprompt.set(preprompt)
        e = discord.Embed(
            title=f"Image preprompt set for {mention_type.name.lower()}:",
            description=truncate_prompt(preprompt),
            color=await ctx.embed_color(),
        )
        await add_prompt_metrics_fields(e, self.services, ctx, preprompt)
        return await ctx.send(embed=e)

    @imagerequest_preprompt.command(name="clear")
    async def imagerequest_preprompt_clear(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Clear an image preprompt so broader settings can apply"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.function_calling_image_preprompt.set(None)
        return await ctx.send(
            f"Image preprompt cleared for this {mention_type.name.lower()}."
        )
