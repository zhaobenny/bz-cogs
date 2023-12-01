import importlib
import logging

import discord
from redbot.core import checks, commands

from aiuser.abc import MixinMeta, aiuser
from aiuser.common.constants import VISION_SUPPORTED_MODELS
from aiuser.common.enums import ScanImageMode

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageScanSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def imagescan(self, _):
        """ Change the image scan setting

            Go [here](https://github.com/zhaobenny/bz-cogs/tree/main/aiuser#image-scanning-%EF%B8%8F) for more info.

            (All subcommands are per server)
        """
        pass

    @imagescan.command(name="toggle")
    async def image_scanning(self, ctx: commands.Context):
        """ Toggle image scanning """
        value = not (await self.config.guild(ctx.guild).scan_images())
        await self.config.guild(ctx.guild).scan_images.set(value)
        embed = discord.Embed(
            title="Scanning Images for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @imagescan.command(name="maxsize")
    async def image_maxsize(self, ctx: commands.Context, size: float):
        """ Set max download size in Megabytes for image scanning """
        await self.config.guild(ctx.guild).max_image_size.set(size * 1024 * 1024)
        embed = discord.Embed(
            title="Max download size to scan images now set to:",
            description=f"{size:.2f} MB",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @imagescan.command(name="mode")
    async def image_mode(self, ctx: commands.Context, mode: str):  # Modify the parameter type
        """ Set method for scanning images """
        values = [m.value for m in ScanImageMode]

        if mode not in values:
            await ctx.send(":warning: Invalid mode.")

        if mode == "list" or mode not in values:
            embed = discord.Embed(
                title="Valid modes:",
                description="\n".join(values),
                color=await ctx.embed_color())
            return await ctx.send(embed=embed)

        mode = ScanImageMode(mode)
        if mode == ScanImageMode.LOCAL:
            try:
                importlib.import_module("pytesseract")
                importlib.import_module("torch")
                importlib.import_module("transformers")
                await self.config.guild(ctx.guild).scan_images_mode.set(ScanImageMode.LOCAL.value)
                embed = discord.Embed(title="Scanning Images for this server now set to", color=await ctx.embed_color())
                embed.add_field(
                    name=":warning: __WILL CAUSE HEAVY CPU LOAD__ :warning:", value=mode.value, inline=False)
                return await ctx.send(embed=embed)
            except Exception as e:
                logger.error(
                    "Image processing dependencies import failed. ", exc_info=True)
                await self.config.guild(ctx.guild).scan_images_mode.set(ScanImageMode.AI_HORDE.value)
                return await ctx.send(":warning: Local image processing dependencies not available. Please install them (see cog README.md) to use this feature locally.")
        elif mode == ScanImageMode.AI_HORDE:
            await self.config.guild(ctx.guild).scan_images_mode.set(ScanImageMode.AI_HORDE.value)
            embed = discord.Embed(title="Scanning Images for this server now set to", description=mode.value, color=await ctx.embed_color())
            embed.add_field(
                name=":warning: __PRIVACY WARNING__ :warning:",
                value="This will send images to a random volunteer machine for processing! \n Please inform users or use local mode for privacy.",
                inline=False)
            if (await self.bot.get_shared_api_tokens('ai-horde')).get("api_key"):
                key_description = "Key set."
            else:
                key_description = f"No key set. \n Request will be lower priority.\n  \
                                Create one [here](https://stablehorde.net/#:~:text=0%20alchemy%20forms.-,Usage,-First%20Register%20an)\
                                and set it with `{ctx.clean_prefix}set api ai-horde api_key,API_KEY`"
            embed.add_field(
                name="AI Horde API key:",
                value=key_description,
                inline=False)
            embed.add_field(
                name="Reminder",
                value="AI Horde is a crowdsourced volunteer service. \n Please contribute back if heavily used. See [here](https://stablehorde.net/)",
                inline=False)
            return await ctx.send(embed=embed)
        elif mode == ScanImageMode.LLM:
            model = await self.config.guild(ctx.guild).model()
            if not (model in VISION_SUPPORTED_MODELS):
                return await ctx.send(f":warning: Currently selected model, {model}, does not support image scanning. Set a comptaible model first!")

            await self.config.guild(ctx.guild).scan_images_mode.set(ScanImageMode.LLM.value)
            embed = discord.Embed(title="Scanning Images for this server now set to", description=mode.value, color=await ctx.embed_color())

            embed.add_field(
                name=":warning: __PRIVACY WARNING__ :warning:",
                value="This may send images to OpenAI / third party for processing! \n Please inform users or use local mode for privacy.",
                inline=False)
            return await ctx.send(embed=embed)
