import logging
import re
from typing import Optional
import discord
import openai

from redbot.core import checks, commands


from ai_user.abc import MixinMeta, ai_user
from ai_user.common.constants import DEFAULT_BLOCKLIST, DEFAULT_REMOVELIST

logger = logging.getLogger("red.bz_cogs.ai_user")


class ResponseSettings(MixinMeta):

    @ai_user.group(name="response")
    @checks.admin_or_permissions(manage_guild=True)
    async def response(self, _):
        """ Change bot response settings """
        pass

    @response.command()
    @checks.is_owner()
    async def custom_openai(self, ctx: commands.Context, url: Optional[str]):
        """ Sets a custom OpenAI endpoint """
        if not url:
            openai.api_base = "https://api.openai.com/v1"
            await self.config.custom_openai_endpoint.set(None)
        else:
            await self.config.custom_openai_endpoint.set(url)
            openai.api_base = url

        embed = discord.Embed(title="Bot Custom OpenAI endpoint", color=await ctx.embed_color())
        embed.add_field(
            name=":warning: Warning :warning:", value="All model selections may need changing.", inline=False)

        if url:
            embed.description = f"Endpoint set to {url}."
            embed.add_field(
                name="Models", value="Third party models may have undesirable results, compared to OpenAI.", inline=False)
            embed.add_field(
                name="Note", value="This is an advanced feature. \
                    \n If you don't know what you're doing, don't use it",  inline=False)
        else:
            embed.description = "Endpoint reset back to offical OpenAI endpoint."

        await ctx.send(embed=embed)

    @response.group(name="blocklist")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist(self, _):
        """ Any generated bot messages matching these regex patterns will not sent """

    @blocklist.command(name="add")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_add(self, ctx: commands.Context, regex_pattern: str):
        """Add a regex pattern to the blocklist"""
        try:
            re.compile(regex_pattern)
        except re.error:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")

        blocklist_regexes = await self.config.guild(ctx.guild).blocklist_regexes()

        if regex_pattern not in blocklist_regexes:
            blocklist_regexes.append(regex_pattern)
            await self.config.guild(ctx.guild).blocklist_regexes.set(blocklist_regexes)
            await ctx.send(f"The regex pattern `{regex_pattern}` has been added to the blocklist.")
        else:
            await ctx.send(f"The regex pattern `{regex_pattern}` is already in the blocklist.")

    @blocklist.command(name="remove")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_remove(self, ctx: commands.Context, regex_pattern: str):
        """Remove a regex pattern from the blacklist"""
        blocklist_regexes = await self.config.guild(ctx.guild).blocklist_regexes()

        if regex_pattern in blocklist_regexes:
            blocklist_regexes.remove(regex_pattern)
            await self.config.guild(ctx.guild).blocklist_regexes.set(blocklist_regexes)
            await ctx.send(f"The regex pattern `{regex_pattern}` has been removed from the blocklist.")
        else:
            await ctx.send(f"The regex pattern `{regex_pattern}` is not in the blocklist.")

    @blocklist.command(name="show")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_show(self, ctx: commands.Context):
        """Show the current regex patterns in the blocklist"""
        blocklist_regexes = await self.config.guild(ctx.guild).blocklist_regexes()

        if not blocklist_regexes:
            await ctx.send("The blocklist is empty.")
        else:
            formatted_list = "\n".join(blocklist_regexes)
            await ctx.send(f"The current regex patterns in the blocklist are:\n```\n{formatted_list}\n```")

    @blocklist.command(name="reset")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_reset(self, ctx: commands.Context):
        """Reset the blocklist to default """
        await self.config.guild(ctx.guild).blocklist_regexes.set(DEFAULT_BLOCKLIST)
        await ctx.send("The message blocklist has been reset.")

    @response.group(name="removelist")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist(self, _):
        """ Any string in generated bot messages matching these regex patterns will be removed """

    @removelist.command(name="add")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_add(self, ctx: commands.Context, regex_pattern: str):
        """Add a regex pattern to the removelist"""
        try:
            re.compile(regex_pattern)
        except re.error:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")

        removelist_regexes = await self.config.guild(ctx.guild).removelist_regexes()

        if regex_pattern not in removelist_regexes:
            removelist_regexes.append(regex_pattern)
            await self.config.guild(ctx.guild).removelist_regexes.set(removelist_regexes)
            await ctx.send(f"The regex pattern `{regex_pattern}` has been added to the removelist.")
        else:
            await ctx.send(f"The regex pattern `{regex_pattern}` is already in the removelist.")

    @removelist.command(name="remove")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_remove(self, ctx: commands.Context, regex_pattern: str):
        """Remove a regex pattern from the removelist"""
        removelist_regexes = await self.config.guild(ctx.guild).removelist_regexes()

        if regex_pattern in removelist_regexes:
            removelist_regexes.remove(regex_pattern)
            await self.config.guild(ctx.guild).removelist_regexes.set(removelist_regexes)
            await ctx.send(f"The regex pattern `{regex_pattern}` has been removed from the removelist.")
        else:
            await ctx.send(f"The regex pattern `{regex_pattern}` is not in the removelist.")

    @removelist.command(name="show")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_show(self, ctx: commands.Context):
        """Show the current regex patterns in the removelist"""
        removelist_regexes = await self.config.guild(ctx.guild).removelist_regexes()

        if not removelist_regexes:
            await ctx.send("The removelist is empty.")
        else:
            formatted_list = "\n".join(removelist_regexes)
            await ctx.send(f"The current regex patterns in the removelist are:\n```\n{formatted_list}\n```")

    @removelist.command(name="reset")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_reset(self, ctx: commands.Context):
        """Reset the removelist to default """
        await self.config.guild(ctx.guild).removelist_regexes.set(DEFAULT_REMOVELIST)
        await ctx.send("The message removelist has been reset.")
