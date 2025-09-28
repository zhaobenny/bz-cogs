import logging

import discord
from redbot.core import checks, commands

from aiuser.config.constants import OPENROUTER_URL
from aiuser.config.models import VISION_SUPPORTED_MODELS
from aiuser.types.abc import MixinMeta, aiuser

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageScanSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def imagescan(self, _):
        """ Change the image scan setting
        """
        pass

    @imagescan.command(name="toggle")
    async def image_scanning(self, ctx: commands.Context):
        """ Toggle image scanning """
        value = not (await self.config.guild(ctx.guild).scan_images())
        await self.config.guild(ctx.guild).scan_images.set(value)
        embed = discord.Embed(
            title="Scanning Images for this server now set to:",
            description=f"`{value}`",
            color=await ctx.embed_color())
        if value:
            embed.add_field(
                name="👁️ __PRIVACY WARNING__",
                value="This will send image attachments to the specified endpoint for processing!",
                inline=False)
            scan_model = await self.config.guild(ctx.guild).scan_images_model()
            model = scan_model or await self.config.guild(ctx.guild).model()
            if model not in VISION_SUPPORTED_MODELS:
                embed.add_field(
                    name=":warning: Unvalidated Model",
                    value=f"The current model `{model}` has not been validated for image scanning.",
                    inline=False)
        return await ctx.send(embed=embed)

    @imagescan.command(name="maxsize")
    async def image_maxsize(self, ctx: commands.Context, size: float):
        """ Set max download size in Megabytes for image scanning """
        await self.config.guild(ctx.guild).max_image_size.set(size * 1024 * 1024)
        embed = discord.Embed(
            title="Max download size to scan images now set to:",
            description=f"`{size:.2f}` MB",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @imagescan.command(name="model")
    async def image_model(self, ctx: commands.Context, model_name: str):
        """ Set a specific LLM for image scanning, or `reset` to use the main model """
        if model_name.lower() == "reset":
            await self.config.guild(ctx.guild).scan_images_model.set(None)
            embed = discord.Embed(
                title="LLM for scanning images reset.",
                description="The main model will be used for image scanning.",
                color=await ctx.embed_color())
            return await ctx.send(embed=embed)

        custom_endpoint = await self.config.custom_openai_endpoint()
        warning_message = None

        if (not custom_endpoint or custom_endpoint.startswith(OPENROUTER_URL)):
            await ctx.message.add_reaction("🔄")
            models = [model.id for model in (await self.openai_client.models.list()).data]
            models = list(set(models) & set(VISION_SUPPORTED_MODELS))
            await ctx.message.remove_reaction("🔄", ctx.me)

            if model_name not in models:
                warning_message = "⚠️ Model has not been validated for image scanning."

        await self.config.guild(ctx.guild).scan_images_model.set(model_name)
        embed = discord.Embed(
            title="LLM for scanning images now set to:",
            description=f"`{model_name}`",
            color=await ctx.embed_color())
        if warning_message:
            embed.set_footer(text=warning_message)
        return await ctx.send(embed=embed)