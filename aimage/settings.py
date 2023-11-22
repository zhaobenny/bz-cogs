from typing import Optional

import discord
from redbot.core import checks, commands

from aimage.abc import MixinMeta


class Settings(MixinMeta):

    @commands.group(name="aimage", aliases=["image"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def aimage(self, _: commands.Context):
        """Manage AI Image cog settings"""
        pass

    @aimage.command(name="config")
    async def config(self, ctx: commands.Context):
        """
        Show the current AI Image config
        """
        guild = ctx.guild
        config = await self.config.guild(guild).get_raw()

        embed = discord.Embed(title="AI Image Config", color=await ctx.embed_color())
        embed.add_field(name="Endpoint", value=config["endpoint"])
        embed.add_field(name="Blacklisted words", value=(", ".join(
            config["words_blacklist"]) or "None"), inline=False)
        embed.add_field(name="Default negative Prompt",
                        value=config["negativeprompt"], inline=False)

        return await ctx.send(embed=embed)

    @aimage.command(name="endpoint")
    async def endpoint(self, ctx: commands.Context, endpoint: str):
        """
        Set the endpoint URL for AI Image (include `/sdapi/v1/txt2img` for Automatic1111 URLs)
        """
        await self.config.guild(ctx.guild).endpoint.set(endpoint)
        await ctx.tick()

    @aimage.command(name="blacklist")
    async def blacklist(self, ctx: commands.Context, words: Optional[str]):
        """
        Set the blacklist of words from that will be reject the prompt
        Comma separated eg. `red,blue,green`
        """
        if words:
            words = words.split(",")
        await self.config.guild(ctx.guild).words_blacklist.set(words)

        embed = discord.Embed(title="The blacklisted words are now:",
                              description=", ".join(words), color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @aimage.command(name="negativeprompt")
    async def negativeprompt(self, ctx: commands.Context, negativeprompt: str):
        """
        Set the default negative prompt
        """
        await self.config.guild(ctx.guild).negativeprompt.set(negativeprompt)
        await ctx.tick()

    @aimage.command(name="cfg")
    async def cfg(self, ctx: commands.Context, cfg: int):
        """
        Set the default cfg
        """
        await self.config.guild(ctx.guild).cfg.set(cfg)
        await ctx.tick()

    @commands.group(name="aimageowner", aliases=["imageowner"])
    @checks.is_owner()
    async def aimageowner(self, _: commands.Context):
        """Manage AI Image owner settings"""
        pass

    @aimageowner.command(name="endpoint")
    async def endpoint_owner(self, ctx: commands.Context, endpoint: str):
        """
        Set a global endpoint URL for AI Image (include `/sdapi/v1/txt2img` for Automatic1111 URLs)

        Will be used if no guild endpoint is set
        """
        await self.config.endpoint.set(endpoint)
        await ctx.tick()

    @aimageowner.command(name="blacklist")
    async def blacklist_owner(self, ctx: commands.Context, words: Optional[str]):
        """
        Set a global blacklist of words from that will be reject the prompt in any servers
        Comma separated eg. `red,blue,green`
        """
        if words:
            words = words.split(",")
        await self.config.words_blacklist.set(words)

        embed = discord.Embed(title="The blacklisted words are now:",
                              description=", ".join(words), color=await ctx.embed_color())
        return await ctx.send(embed=embed)
