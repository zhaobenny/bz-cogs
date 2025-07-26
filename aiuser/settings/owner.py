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

from aiuser.config.defaults import DEFAULT_LLM_MODEL
from aiuser.core.openai_utils import setup_openai_client
from aiuser.settings.utilities import get_tokens, truncate_prompt
from aiuser.types.abc import MixinMeta
from aiuser.types.enums import ScanImageMode
from aiuser.utils.utilities import (
    is_using_openai_endpoint,
    is_using_openrouter_endpoint,
)

logger = logging.getLogger("red.bz_cogs.aiuser")


class OwnerSettings(MixinMeta):
    @commands.group(aliases=["ai_userowner"])
    @checks.is_owner()
    async def aiuserowner(self, _):
        """For some settings that apply bot-wide."""
        pass

    @aiuserowner.command(name="maxpromptlength")
    async def max_prompt_length(self, ctx: commands.Context, length: int):
        """Sets the maximum character length of a prompt that can set by admins in any server.

        (Does not apply to already set prompts, only new ones)
        """
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
        """Sets the maximum character length of a random prompt that can set by any server.

        (Does not apply to already set prompts, only new ones)
        """
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
        """Sets the OpenAI endpoint to a custom url (must be OpenAI API compatible)

        **Arguments:**
        - `url`: The url to set the endpoint to.
        OR
        - `openai`, `openrouter`, `ollama`: Shortcuts for the default endpoints. (localhost for ollama)
        """

        if url == "openrouter":
            url = "https://openrouter.ai/api/v1/"
        elif url == "ollama":
            url = "http://localhost:11434/v1/"
        elif url in ["clear", "reset", "openai"]:
            url = None

        previous_url = await self.config.custom_openai_endpoint()

        # Save current models before switching
        if previous_url:
            history = await self.config.endpoint_model_history()
            history[previous_url] = {}
            for guild_id in await self.config.all_guilds():
                guild_config = self.config.guild_from_id(guild_id)
                history[previous_url][str(guild_id)] = {
                    "chat_model": await guild_config.model(),
                    "image_model": await guild_config.scan_images_model(),
                }
            await self.config.endpoint_model_history.set(history)

        await self.config.custom_openai_endpoint.set(url)

        await ctx.message.add_reaction("🔄")

        self.openai_client = await setup_openai_client(self.bot, self.config)

        # test the endpoint works if not rollback
        try:
            models = await self.openai_client.models.list()
        except Exception:
            await self.config.custom_openai_endpoint.set(previous_url)
            return await ctx.send(
                ":warning: Invalid endpoint. Please check logs for more information."
            )
        finally:
            await ctx.message.remove_reaction("🔄", ctx.me)

        # Check if we have saved models for this endpoint
        history = await self.config.endpoint_model_history()
        saved_models = history.get(url or "default", {})

        chat_model = DEFAULT_LLM_MODEL
        image_model = DEFAULT_LLM_MODEL

        if is_using_openrouter_endpoint(self.openai_client):
            chat_model = f"openai/{DEFAULT_LLM_MODEL}"
            image_model = f"openai/{DEFAULT_LLM_MODEL}"
        elif not is_using_openai_endpoint(self.openai_client):
            chat_model = models.data[0].id
            image_model = models.data[0].id

        embed = discord.Embed(title="Bot Custom OpenAI endpoint", color=await ctx.embed_color())

        restored_count = 0
        guilds_with_parameters = []
        for guild_id in await self.config.all_guilds():
            guild_config = self.config.guild_from_id(guild_id)

            # Restore saved models if available, otherwise use defaults
            if str(guild_id) in saved_models:
                await guild_config.model.set(saved_models[str(guild_id)]["chat_model"])
                await guild_config.scan_images_model.set(saved_models[str(guild_id)]["image_model"])
                restored_count += 1
            else:
                await guild_config.model.set(chat_model)
                await guild_config.scan_images_model.set(image_model)

            if await guild_config.parameters():
                guilds_with_parameters.append(str(self.bot.get_guild(guild_id).name))

        if restored_count > 0:
            total_guilds = len(await self.config.all_guilds())
            value = f"Restored previously set models on this endpoint for {restored_count} servers."
            if restored_count < total_guilds:
                value += f"\nA further {total_guilds - restored_count} servers were set to `{chat_model}` for chat, and \n`{image_model}` for scanning images if set to `{ScanImageMode.LLM.value}` mode."
            embed.add_field(
                name="🔄 Restored",
                value=value,
                inline=False,
            )
        else:
            embed.add_field(
                name="🔄 Reset",
                value=f"All per-server models have been set to use `{chat_model}` for chat \n and `{image_model}` for scanning images if set to `{ScanImageMode.LLM.value}` mode.",
                inline=False,
            )

        if guilds_with_parameters:
            embed.add_field(
                name=":warning: Caution",
                value=f"Custom parameters have been set in the following servers: `{', '.join(guilds_with_parameters)}`\nThey may not work with the new endpoint!",
                inline=False,
            )

        if url:
            embed.description = f"Endpoint set to {url}."
            embed.set_footer(
                text="❗ Third party models may have undesirable results with this cog."
            )
        else:
            embed.description = "Endpoint reset back to offical OpenAI endpoint."

        await ctx.send(embed=embed)

    @aiuserowner.command()
    async def timeout(self, ctx: commands.Context, seconds: int):
        """Sets the request timeout to the OpenAI endpoint"""

        if seconds < 1:
            return await ctx.send(":warning: Please enter a positive integer.")

        await self.config.openai_endpoint_request_timeout.set(seconds)
        await self.initialize_openai_client()

        embed = discord.Embed(
            title="The request timeout is now:",
            description=f"`{seconds}` seconds",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @aiuserowner.command(name="exportconfig")
    async def export_config(self, ctx: commands.Context):
        """Exports the current config to a json file

        :warning: JSON backend only
        """
        path = Path(cog_data_path(self) / "settings.json")

        if not path.exists():
            return await ctx.send(":warning: Export is only supported for json backends")

        await ctx.send(file=discord.File(path, filename="aiuser_config.json"))
        await ctx.tick()

    @aiuserowner.command(name="importconfig")
    async def import_config(self, ctx: commands.Context):
        """Imports a config from json file (:warning: No checks are done)

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
            color=await ctx.embed_color(),
        )
        confirm = await ctx.send(embed=embed)
        start_adding_reactions(confirm, ReactionPredicate.YES_OR_NO_EMOJIS)
        pred = ReactionPredicate.yes_or_no(confirm, ctx.author)
        try:
            await ctx.bot.wait_for("reaction_add", timeout=30.0, check=pred)
        except asyncio.TimeoutError:
            return await confirm.edit(
                embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color())
            )
        if pred.result is False:
            return await confirm.edit(
                embed=discord.Embed(title="Cancelled.", color=await ctx.embed_color())
            )

        with path.open("w") as f:
            json.dump(new_config, f, indent=4)

        return await confirm.edit(
            embed=discord.Embed(
                title="Overwritten!",
                description="You will need to restart the bot for the changes to take effect.",
                color=await ctx.embed_color(),
            )
        )

    @aiuserowner.command(name="prompt")
    async def global_prompt(self, ctx: commands.Context, *, prompt: Optional[str]):
        """Set the global default prompt for aiuser.

        Leave blank to delete the currently set global prompt, and use the build-in default prompt.

        **Arguments**
            - `prompt` The prompt to set.
        """
        if not prompt and ctx.message.attachments:
            if not ctx.message.attachments[0].filename.endswith(".txt"):
                return await ctx.send(":warning: Invalid attachment. Must be a `.txt` file.")
            prompt = (await ctx.message.attachments[0].read()).decode("utf-8")

        if not prompt:
            await self.config.custom_text_prompt.set(None)
            return await ctx.send("The global prompt is now reset to the default prompt")

        await self.config.custom_text_prompt.set(prompt)

        embed = discord.Embed(
            title="The global prompt is now changed to:",
            description=f"{truncate_prompt(prompt)}",
            color=await ctx.embed_color(),
        )
        embed.add_field(name="Tokens", value=await get_tokens(self.config, ctx, prompt))
        return await ctx.send(embed=embed)
