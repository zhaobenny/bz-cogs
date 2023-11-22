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

        embed = discord.Embed(title="AImage Config", color=await ctx.embed_color())
        embed.add_field(name="Endpoint", value=config["endpoint"])
        embed.add_field(name="Default negative prompt",
                        value=config["negativeprompt"], inline=False)
        blacklist = ", ".join(config["words_blacklist"])
        if len(blacklist) > 1024:
            blacklist = blacklist[:1020] + "..."
        embed.add_field(name="Blacklisted words",
                        value=blacklist, inline=False)

        return await ctx.send(embed=embed)

    @aimage.command(name="endpoint")
    async def endpoint(self, ctx: commands.Context, endpoint: str):
        """
        Set the endpoint URL for AI Image (include `/sdapi/v1/txt2img` for Automatic1111 URLs)
        """
        await self.config.guild(ctx.guild).endpoint.set(endpoint)
        await ctx.tick()

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

    @aimage.group(name="blacklist")
    async def blacklist(self, _: commands.Context):
        """
        Manage the blacklist of words that will be rejected in prompts
        """
        pass

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, *words: str):
        """
        Add words to the blacklist

        (Separate multiple words with spaces)
        """
        current_words = await self.config.guild(ctx.guild).words_blacklist()
        added = []
        for word in words:
            if word not in current_words:
                added.append(word)
                current_words.append(word)
        if not added:
            return await ctx.send("No words added")
        await self.config.guild(ctx.guild).words_blacklist.set(current_words)
        return await ctx.send(f"Added words `{', '.join(added)}` to blacklist")

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, *words: str):
        """
        Remove words from the blacklist

        (Separate multiple words with spaces)
        """
        current_words = await self.config.guild(ctx.guild).words_blacklist()

        removed = []
        for word in words:
            if word in current_words:
                removed.append(word)
                current_words.remove(word)
        if not removed:
            return await ctx.send("No words removed")
        await self.config.guild(ctx.guild).words_blacklist.set(current_words)
        return await ctx.send(f"Removed words `{', '.join(removed)}` from blacklist")

    @blacklist.command(name="clear")
    async def blacklist_clear(self, ctx: commands.Context):
        """
        Clear the blacklist to nothing!
        """
        await self.config.guild(ctx.guild).words_blacklist.set([])
        await ctx.tick()

    @commands.group(name="aimageowner", aliases=["imageowner"])
    @checks.is_owner()
    async def aimageowner(self, _: commands.Context):
        """Manage AI Image owner settings"""
        pass

    @aimageowner.command(name="config")
    async def config_owner(self, ctx: commands.Context):
        """
        Show the current AI Image config
        """
        config = await self.config.get_raw()

        embed = discord.Embed(title="Global AImage Config", color=await ctx.embed_color())
        embed.add_field(name="Endpoint", value=config["endpoint"])
        blacklist = ", ".join(config["words_blacklist"])
        if len(blacklist) > 1024:
            blacklist = blacklist[:1020] + "..."
        embed.add_field(name="Blacklisted words",
                        value=blacklist, inline=False)

        return await ctx.send(embed=embed)

    @aimageowner.command(name="endpoint")
    async def endpoint_owner(self, ctx: commands.Context, endpoint: str):
        """
        Set a global endpoint URL for AI Image (include `/sdapi/v1/txt2img` for Automatic1111 URLs)

        Will be used if no guild endpoint is set
        """
        await self.config.endpoint.set(endpoint)
        await ctx.tick()

    @aimageowner.group(name="blacklist")
    async def blacklist_owner(self, _: commands.Context):
        """
        Manage the blacklist of words that will be rejected in prompts when using the global endpoint

        (Separate multiple words with spaces)
        """
        pass

    @blacklist_owner.command(name="add")
    async def blacklist_add_owner(self, ctx: commands.Context, *words: str):
        """
        Add words to the global blacklist

        (Separate multiple words with spaces)
        """
        current_words = await self.config.words_blacklist()
        added = []
        for word in words:
            if word not in current_words:
                added.append(word)
                current_words.append(word)
        if not added:
            return await ctx.send("No words added")

        await self.config.words_blacklist.set(current_words)
        return await ctx.send(f"Added words `{', '.join(added)}` to blacklist")

    @blacklist_owner.command(name="remove")
    async def blacklist_remove_owner(self, ctx: commands.Context, *words: str):
        """
        Remove words from the global blacklist

        (Separate multiple words with spaces)
        """
        current_words = await self.config.words_blacklist()
        removed = []
        for word in words:
            if word in current_words:
                removed.append(word)
                current_words.remove(word)
        if not removed:
            return await ctx.send("No words removed")

        await self.config.words_blacklist.set(current_words)
        await ctx.send(f"Removed words `{words}` to global blacklist")

    @blacklist_owner.command(name="clear")
    async def blacklist_clear_owner(self, ctx: commands.Context):
        """
        Clear the global blacklist to nothing!
        """
        await self.config.words_blacklist.set([])
        await ctx.tick()

    @commands.guild_only()
    @blacklist_owner.command()
    async def forcesync(self, ctx: commands.Context):
        """
        Force sync slash commands (mainly for development usage)
        """
        self.bot.tree.copy_global_to(
            guild=discord.Object(id=ctx.guild.id))
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Force synced {len(synced)} commands")
