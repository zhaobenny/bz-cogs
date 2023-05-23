import importlib
import logging

import discord
from redbot.core import checks, commands

from ai_user.abc import MixinMeta, ai_user
from ai_user.common.constants import (AI_HORDE_MODE, LOCAL_MODE,
                                      SCAN_IMAGE_MODES)
logger = logging.getLogger("red.bz_cogs.ai_user")


class ImageSettings(MixinMeta):
    @ai_user.group()
    @checks.is_owner()
    async def image(self, _):
        """ Change the image scan setting for the current server. (See cog README.md) """
        pass

    @image.command(name="scan")
    @checks.is_owner()
    async def image_scanning(self, ctx: commands.Context):
        """ Toggle image scanning for the current server """
        value = not (await self.config.guild(ctx.guild).scan_images())
        await self.config.guild(ctx.guild).scan_images.set(value)
        embed = discord.Embed(
            title="Scanning Images for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @image.command(name="maxsize")
    @checks.is_owner()
    async def image_maxsize(self, ctx: commands.Context, new_value: float):
        """ Set max download size in Megabytes for image scanning """
        await self.config.guild(ctx.guild).max_image_size.set(new_value * 1024 * 1024)
        embed = discord.Embed(
            title="Max download size to scan images now set to:",
            description=f"{new_value:.2f} MB",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @image.command(name="mode")
    @checks.is_owner()
    async def image_mode(self, ctx: commands.Context, new_value: str):
        """ Set method to scan, local or ai-horde (see cog README.md) """
        if new_value not in SCAN_IMAGE_MODES:
            await ctx.send(f"Invalid mode. Choose from: {', '.join(SCAN_IMAGE_MODES)}")
        elif new_value == LOCAL_MODE:
            try:
                importlib.import_module("pytesseract")
                importlib.import_module("torch")
                importlib.import_module("transformers")
                await self.config.guild(ctx.guild).scan_images_mode.set(new_value)
                embed = discord.Embed(title="Scanning Images for this server now set to", color=await ctx.embed_color())
                embed.add_field(name=":warning: WILL CAUSE HEAVY CPU LOAD :warning:", value=new_value, inline=False)
                return await ctx.send(embed=embed)
            except:
                logger.error("Image processing dependencies import failed. ", exc_info=True)
                await self.config.guild(ctx.guild).scan_images_mode.set(AI_HORDE_MODE)
                return await ctx.send("Local image processing dependencies not available. Please install them (see cog README.md) to use this feature locally.")
        elif new_value == AI_HORDE_MODE:
            await self.config.guild(ctx.guild).scan_images_mode.set(AI_HORDE_MODE)
            embed = discord.Embed(title="Scanning Images for this server now set to", description=new_value, color=await ctx.embed_color())
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
