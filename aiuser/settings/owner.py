import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

from aiuser.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


class OwnerSettings(MixinMeta):
    @commands.group(aliases=["ai_userowner"])
    @checks.is_owner()
    async def aiuserowner(self, _):
        """For some settings that apply bot-wide."""
        pass

    @aiuserowner.command(name="maxpromptlength")
    async def max_prompt_length(self, ctx: commands.Context, length: int):
        """Sets the maximum character length of a prompt that can set by admins in any server."""
        if length < 1:
            return await ctx.send("Please enter a positive integer.")
        await self.config.max_prompt_length.set(length)
        embed = discord.Embed(
            title="The maximum prompt length is now:",
            description=f"{length}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @aiuserowner.command(name="maxtopiclength")
    async def max_random_prompt_length(self, ctx: commands.Context, length: int):
        """Sets the maximum character length of a random prompt that can set by any server."""
        if length < 1:
            return await ctx.send("Please enter a positive integer.")
        await self.config.max_random_prompt_length.set(length)
        embed = discord.Embed(
            title="The maximum topic length is now:",
            description=f"{length}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @aiuserowner.command()
    async def endpoint(self, ctx: commands.Context, url: Optional[str]):
        """Sets the OpenAI endpoint to a custom one (must be OpenAI API compatible)

        Reset to official OpenAI endpoint with `[p]aiuseradmin endpoint clear`
        """
        if not url or url in ["clear", "reset"]:
            await self.config.custom_openai_endpoint.set(None)
            await self.initialize_openai_client()
        else:
            await self.config.custom_openai_endpoint.set(url)
            await self.initialize_openai_client()

        embed = discord.Embed(
            title="Bot Custom OpenAI endpoint", color=await ctx.embed_color()
        )
        embed.add_field(
            name=":warning: Warning :warning:",
            value="All model/parameters selections for each server may need changing.",
            inline=False,
        )

        if url:
            embed.description = f"Endpoint set to {url}."
            embed.add_field(
                name="Models",
                value="Third party models may have undesirable results, compared to OpenAI.",
                inline=False,
            )
        else:
            embed.description = "Endpoint reset back to offical OpenAI endpoint."

        await ctx.send(embed=embed)

    @aiuserowner.command(name="exportconfig")
    async def export_config(self, ctx: commands.Context):
        """Exports the current config to a json file

           :warning: JSON backend only
        """
        path = Path(cog_data_path(self) / "settings.json")

        if not path.exists():
            return await ctx.send(":warning: Export is only supported for json backends")

        await ctx.send(
            file=discord.File(path, filename="aiuser_config.json")
        )
        await ctx.tick()

    @aiuserowner.command(name="importconfig")
    async def import_config(self, ctx: commands.Context):
        """ Imports a config from json file (:warning: No checks are done)

            Make sure your new config is valid, and the old config is backed up.

           :warning: JSON backend only
        """
        if not ctx.message.attachments:
            return await ctx.send(":warning: No file was attached.")

        file = ctx.message.attachments[0]
        try:
            new_config = json.loads(await file.read())
        except json.JSONDecodeError:
            return await ctx.send(":warning: Invalid JSON format!")

        path = Path(cog_data_path(self) / "settings.json")

        if not path.exists():
            return await ctx.send(":warning: Import is only supported for json backends")

        embed = discord.Embed(
            title="Have you backed up your current config?",
            description=f":warning: This will overwrite the current config, and you will lose existing settings! \
                \n :warning: You may also break the cog or bot, if the config is invalid. \
                \n To fix, make sure you can access the config file: \n `{path}`",
            color=await ctx.embed_color())
        confirm = await ctx.send(embed=embed)
        start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", timeout=30.0, check=pred)
        except asyncio.TimeoutError:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))
        if pred.result is False:
            return await confirm.edit(embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color()))

        with path.open("w") as f:
            json.dump(new_config, f, indent=4)

        return await confirm.edit(embed=discord.Embed(
            title="Overwritten!",
            description="You will need to restart the bot for the changes to take effect.",
            color=await ctx.embed_color()))
