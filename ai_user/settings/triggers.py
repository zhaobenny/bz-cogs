import logging
import re
from typing import Optional

import discord

from redbot.core import checks, commands
from ai_user.abc import MixinMeta, ai_user

logger = logging.getLogger("red.bz_cogs.ai_user")


class TriggerSettings(MixinMeta):
    @ai_user.group()
    async def trigger(self, _):
        """ Configure trigger settings for the bot to respond to """
        pass

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    @checks.admin_or_permissions(manage_guild=True)
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """ Messages matching this regex won't be replied to by the bot """
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        await self.config.guild(ctx.guild).ignore_regex.set(regex_pattern)
        embed = discord.Embed(
            title="The ignore regex is now:",
            description=f"`{regex_pattern}`",
            color=await ctx.embed_color())
        await ctx.send(embed=embed)

    @trigger.command(name="force_reply_to_mentions", aliases=["mentions_replies"])
    @checks.is_owner()
    async def force_reply_to_mentions(self, ctx: commands.Context):
        """ Toggles if the bot will always reply to mentions/replies """
        value = not await self.config.guild(ctx.guild).reply_to_mentions_replies()
        await self.config.guild(ctx.guild).reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title="Always replying to mentions or replies for this server now set to:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @trigger.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def public_forget(self, ctx: commands.Context):
        """ Toggles whether anyone can use the forget command, or only moderators """
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

