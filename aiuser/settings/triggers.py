import logging
import re
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from aiuser.abc import MixinMeta, aiuser

logger = logging.getLogger("red.bz_cogs.aiuser")


class TriggerSettings(MixinMeta):
    @checks.admin_or_permissions(manage_guild=True)
    @aiuser.group()
    async def trigger(self, _):
        """ Configure trigger settings for the bot to respond to

            (All subcommands per server)
        """
        pass

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """ Messages matching this regex won't be replied to or seen, by the bot """
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

    @trigger.command(name="reply_to_mentions", aliases=["mentions_replies"])
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
    async def public_forget(self, ctx: commands.Context):
        """ Toggles whether anyone can use the forget command, or only moderators """
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @trigger.group()
    async def random(self, _):
        """ Configure the random trigger

            Every 33 minutes, a RNG roll will determine if a random message will be sent using a list of topics as a prompt.
            The chosen channel must have a hour pass without a message sent in it for a random message to be sent.

            (All subcommands per server)
        """
        pass

    @random.command(name="toggle")
    @checks.is_owner()
    async def random_toggle(self, ctx: commands.Context):
        """ Toggles random message trigger """
        value = not await self.config.guild(ctx.guild).random_messages_enabled()
        await self.config.guild(ctx.guild).random_messages_enabled.set(value)
        embed = discord.Embed(
            title="Senting of random messages:",
            description=f"{value}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @random.command(name="percent", aliases=["set", "chance"])
    @checks.is_owner()
    async def set_random_rng(self, ctx: commands.Context, percent: float):
        """ Sets the chance that a random message will be sent every 33 minutes

            **Arguments**
                - `percent` A number between 0 and 100
        """
        await self.config.guild(ctx.guild).random_messages_percent.set(percent / 100)
        embed = discord.Embed(
            title="The chance that a random message will be sent is:",
            description=f"{percent:.2f}%",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)
