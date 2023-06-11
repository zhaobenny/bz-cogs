import logging
import re
from typing import Optional

import discord
import openai
from redbot.core import checks, commands
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.menus import SimpleMenu

from ai_user.abc import MixinMeta, ai_user
from ai_user.common.constants import DEFAULT_BLOCKLIST, DEFAULT_REMOVELIST

logger = logging.getLogger("red.bz_cogs.ai_user")


class ResponseSettings(MixinMeta):

    @ai_user.group(name="response")
    @checks.admin_or_permissions(manage_guild=True)
    async def response(self, _):
        """ Change bot response settings

            (All subcommands are per server)
        """
        pass

    @response.command()
    @checks.is_owner()
    async def endpoint(self, ctx: commands.Context, url: Optional[str]):
        """ Sets the OpenAI endpoint to a custom one (must be OpenAI API compatible)

            Reset to official OpenAI endpoint with `[p]ai_user response endpoint clear`
        """
        if not url or url in ["clear", "reset"]:
            openai.api_base = "https://api.openai.com/v1"
            await self.config.custom_openai_endpoint.set(None)
        else:
            await self.config.custom_openai_endpoint.set(url)
            openai.api_base = url

        embed = discord.Embed(title="Bot Custom OpenAI endpoint", color=await ctx.embed_color())
        embed.add_field(
            name=":warning: Warning :warning:", value="All model/parameters selections for each server may need changing.", inline=False)

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
        """ Any generated responses matching these regex patterns will not sent """

    @blocklist.command(name="add")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_add(self, ctx: commands.Context, *, regex_pattern: str):
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
    async def blocklist_remove(self, ctx: commands.Context, *, regex_pattern: str):
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
        pages = []

        if not blocklist_regexes:
            return await ctx.send("The blocklist is empty.")

        formatted_list = "\n".join(blocklist_regexes)
        for text in pagify(formatted_list, page_length=888):
            page = discord.Embed(
                title=f"List of regexs to block for bot messages in {ctx.guild.name}",
                description=box(text),
                color=await ctx.embed_color())
            pages.append(page)

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        return await SimpleMenu(pages).start(ctx)

    @blocklist.command(name="reset")
    @checks.admin_or_permissions(manage_guild=True)
    async def blocklist_reset(self, ctx: commands.Context):
        """Reset the blocklist to default """
        await self.config.guild(ctx.guild).blocklist_regexes.set(DEFAULT_BLOCKLIST)
        await ctx.send("The message blocklist has been reset.")

    @response.group(name="removelist")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist(self, _):
        """ Any string in a generated response matching these regex patterns will be removed """

    @removelist.command(name="add")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_add(self, ctx: commands.Context, *, regex_pattern: str):
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
    async def removelist_remove(self, ctx: commands.Context, *, regex_pattern: str):
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
            return await ctx.send("The removelist is empty.")

        pages = []

        formatted_list = "\n".join(removelist_regexes)
        for text in pagify(formatted_list, page_length=888):
            page = discord.Embed(
                title=f"List of regexs to remove for bot messages in {ctx.guild.name}",
                description=box(text),
                color=await ctx.embed_color())
            pages.append(page)

        for i, page in enumerate(pages):
            page.set_footer(text=f"Page {i+1} of {len(pages)}")

        return await SimpleMenu(pages).start(ctx)

    @removelist.command(name="reset")
    @checks.admin_or_permissions(manage_guild=True)
    async def removelist_reset(self, ctx: commands.Context):
        """Reset the removelist to default """
        await self.config.guild(ctx.guild).removelist_regexes.set(DEFAULT_REMOVELIST)
        await ctx.send("The message removelist has been reset.")
