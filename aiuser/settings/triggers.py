import logging
import re
from typing import Optional, Union

import discord
from redbot.core import checks, commands

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

    @trigger.command(name="minlength", aliases=["min_length"])
    async def min_length(self, ctx: commands.Context, length: int):
        """ Set the minimum length of messages that the bot will respond to"""
        await self.config.guild(ctx.guild).messages_min_length.set(length)
        embed = discord.Embed(
            title="The minimum length is now:",
            description=f"{length}",
            color=await ctx.embed_color())
        return await ctx.send(embed=embed)

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """ Messages matching this regex won't be replied to or seen, by the bot """
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except Exception:
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

    @trigger.group(name="whitelist", aliases=["whitelists"])
    async def trigger_whitelist(self, ctx: commands.Context):
        """ If configured, only whitelisted roles / users can trigger a response in whitelisted channels
        """
        pass

    @trigger_whitelist.command(name="add")
    async def trigger_whitelist_add(self, ctx: commands.Context, new: Union[discord.Role, discord.Member]):
        """ Add a role/user to the whitelist """
        if isinstance(new, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if new.id in whitelist:
                return await ctx.send("That role is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(new, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if new.id in whitelist:
                return await ctx.send("That user is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)

        return await self.show_trigger_whitelist(ctx, discord.Embed(
            title="The whitelist is now:",
            color=await ctx.embed_color()))

    @trigger_whitelist.command(name="remove")
    async def trigger_whitelist_remove(self, ctx: commands.Context, rm: Union[discord.Role, discord.Member]):
        """ Remove a user/role from the whitelist """
        if isinstance(rm, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That role is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(rm, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That user is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)
        return await self.show_trigger_whitelist(ctx, discord.Embed(
            title="The whitelist is now:",
            color=await ctx.embed_color()))

    @trigger_whitelist.command(name="list", aliases=["show"])
    async def trigger_whitelist_list(self, ctx: commands.Context):
        """ Show the whitelist """
        return await self.show_trigger_whitelist(ctx, discord.Embed(
            title="Whitelist of users/roles that will trigger LLM",
            color=await ctx.embed_color()))

    @trigger_whitelist.command(name="clear")
    async def trigger_whitelist_clear(self, ctx: commands.Context):
        """ Clear the whitelist, allowing anyone to trigger LLM in whitelisted channels """
        await self.config.guild(ctx.guild).roles_whitelist.set([])
        await self.config.guild(ctx.guild).members_whitelist.set([])
        return await ctx.send("The whitelist has been cleared.")

    async def show_trigger_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        roles_whitelist = await self.config.guild(ctx.guild).roles_whitelist()
        users_whitelist = await self.config.guild(ctx.guild).members_whitelist()
        if roles_whitelist:
            embed.add_field(name="Roles", value="\n".join(
                [f"<@&{r}>" for r in roles_whitelist]), inline=False)
        if users_whitelist:
            embed.add_field(name="Users", value="\n".join(
                [f"<@{u}>" for u in users_whitelist]), inline=False)
        if not roles_whitelist and not users_whitelist:
            embed.description = "Nothing whitelisted\nAnyone can trigger bot in whitelisted channels"
        return await ctx.send(embed=embed)
