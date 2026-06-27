import logging

import discord
from redbot.core import checks, commands

from aiuser.config.model_info import get_model_info
from aiuser.llm.registry import list_llm_models
from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageScanSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def imagescan(self, _):
        """Change the image scan setting"""
        pass

    @imagescan.command(name="toggle")
    async def image_scanning(self, ctx: commands.Context):
        """Toggle image scanning"""
        value = not (await self.config.guild(ctx.guild).scan_images())
        await self.config.guild(ctx.guild).scan_images.set(value)
        embed = discord.Embed(
            title="Scanning Images for this server now set to:",
            description=f"`{value}`",
            color=await ctx.embed_color(),
        )
        if value:
            embed.add_field(
                name="👁️ __PRIVACY WARNING__",
                value="This will send image attachments to the specified endpoint for processing!",
                inline=False,
            )
            scan_model = await self.config.guild(ctx.guild).scan_images_model()
            model = scan_model or await self.config.guild(ctx.guild).model()
            if not get_model_info(model).supports_vision:
                embed.set_footer(text="⚠️ Ensure selected model supports vision")
        return await ctx.send(embed=embed)

    @imagescan.command(name="maxsize")
    async def image_maxsize(self, ctx: commands.Context, size: float):
        """Set max download size in Megabytes for image scanning"""
        await self.config.guild(ctx.guild).max_image_size.set(size * 1024 * 1024)
        embed = discord.Embed(
            title="Max download size to scan images now set to:",
            description=f"`{size:.2f}` MB",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @imagescan.command(name="model")
    async def image_model(self, ctx: commands.Context, model_name: str = None):
        """Set a specific LLM for image scanning, or blank to reset to the main model."""
        if model_name is None:
            await self.config.guild(ctx.guild).scan_images_model.set(None)
            embed = discord.Embed(
                title="LLM for scanning images reset.",
                description="The chat model will be used for image scanning.",
                color=await ctx.embed_color(),
            )
            chat_model = await self.config.guild(ctx.guild).model()
            if not get_model_info(chat_model).supports_vision:
                embed.set_footer(
                    text="⚠️ Model has not been validated for image scanning."
                )
            return await ctx.send(embed=embed)

        await ctx.message.add_reaction("🔄")
        models = await list_llm_models(self.services)
        await ctx.message.remove_reaction("🔄", ctx.me)
        models = [model for model in models if get_model_info(model).supports_vision]

        if not models:
            return await ctx.send(
                ":warning: No image scanning models are currently available."
            )

        if model_name == "list":
            return await self._paginate_models(ctx, models)

        if model_name not in models:
            await ctx.send("⚠️ Not a valid image scanning model!")
            return await self._paginate_models(ctx, models, query=model_name)

        await self.config.guild(ctx.guild).scan_images_model.set(model_name)
        embed = discord.Embed(
            title="LLM for scanning images now set to:",
            description=f"`{model_name}`",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)
