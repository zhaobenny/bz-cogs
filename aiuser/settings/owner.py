import json
import logging
from pathlib import Path
from typing import Optional

import discord
from openai import AuthenticationError
from redbot.core import checks, commands
from redbot.core.data_manager import cog_data_path

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.config.defaults import DEFAULT_LLM_MODEL
from aiuser.llm.codex.oauth import (
    CODEX_DEFAULT_MODEL,
    CODEX_ENDPOINT_MODE,
    ensure_valid_codex_oauth,
    exchange_device_authorization,
    is_codex_endpoint_mode,
    normalize_codex_tokens,
    set_codex_oauth,
    start_device_authorization,
)
from aiuser.llm.openai_compatible.client import setup_openai_client
from aiuser.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_api_token_name,
    get_openai_compat_kind,
)
from aiuser.settings.utilities import (
    add_prompt_metrics_fields,
    confirm_pending,
    truncate_prompt,
)
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


class OwnerSettings(MixinMeta):
    @commands.group(aliases=["ai_userowner"])
    @checks.is_owner()
    async def aiuserowner(self, _):
        """For some settings that apply bot-wide."""
        pass

    @aiuserowner.group(
        name="max_prompt_length",
        aliases=["maxpromptlength"],
        invoke_without_command=True,
    )
    async def max_prompt_length(self, ctx: commands.Context):
        """Show the maximum server prompt length"""
        length = await self.config.max_prompt_length()
        return await ctx.maybe_send_embed(
            f"Maximum prompt length: `{length}` characters"
        )

    @max_prompt_length.command(name="set")
    async def max_prompt_length_set(self, ctx: commands.Context, length: int):
        """Set the maximum server prompt length"""
        if length < 1:
            return await ctx.send("Please enter a positive integer.")
        await self.config.max_prompt_length.set(length)
        return await ctx.send(f"Maximum prompt length set to `{length}` characters.")

    @aiuserowner.group(
        name="max_topic_length", aliases=["maxtopiclength"], invoke_without_command=True
    )
    async def max_random_prompt_length(self, ctx: commands.Context):
        """Show the maximum random-message topic length"""
        length = await self.config.max_random_prompt_length()
        return await ctx.maybe_send_embed(
            f"Maximum topic length: `{length}` characters"
        )

    @max_random_prompt_length.command(name="set")
    async def max_random_prompt_length_set(self, ctx: commands.Context, length: int):
        """Set the maximum random-message topic length"""
        if length < 1:
            return await ctx.send("Please enter a positive integer.")
        await self.config.max_random_prompt_length.set(length)
        return await ctx.send(f"Maximum topic length set to `{length}` characters.")

    @aiuserowner.group(name="endpoint", invoke_without_command=True)
    async def endpoint(self, ctx: commands.Context):
        """Show the configured model endpoint"""
        url = await self.config.custom_openai_endpoint()
        return await ctx.maybe_send_embed(f"Model endpoint: `{url or 'OpenAI'}`")

    @endpoint.command(name="set")
    async def endpoint_set(self, ctx: commands.Context, url: str):
        """Set an endpoint URL or a built-in endpoint name"""
        return await self._set_custom_endpoint(ctx, url)

    @endpoint.command(name="clear")
    async def endpoint_clear(self, ctx: commands.Context):
        """Use the default OpenAI endpoint"""
        return await self._set_custom_endpoint(ctx, None)

    @aiuserowner.group(name="timeout", invoke_without_command=True)
    async def timeout(self, ctx: commands.Context):
        """Show the model endpoint request timeout"""
        seconds = await self.config.openai_endpoint_request_timeout()
        return await ctx.maybe_send_embed(
            f"Endpoint request timeout: `{seconds}` seconds"
        )

    @timeout.command(name="set")
    async def timeout_set(self, ctx: commands.Context, seconds: int):
        """Set the model endpoint request timeout"""
        if seconds < 1:
            return await ctx.send(":warning: Please enter a positive integer.")

        await self.config.openai_endpoint_request_timeout.set(seconds)
        self.services.openai_client = await setup_openai_client(self.bot, self.config)

        return await ctx.send(f"Endpoint request timeout set to `{seconds}` seconds.")

    @aiuserowner.group(name="config")
    async def owner_config(self, _):
        """Import or export the complete cog configuration"""
        pass

    @owner_config.command(name="export")
    async def export_config(self, ctx: commands.Context):
        """Exports the current config to a json file

        :warning: JSON backend only
        """
        path = Path(cog_data_path(self) / "settings.json")

        if not path.exists():
            return await ctx.send(
                ":warning: Export is only supported for json backends"
            )

        await ctx.send(file=discord.File(path, filename="aiuser_config.json"))
        await ctx.tick()

    @owner_config.command(name="import")
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
            return await ctx.send(
                ":warning: Import is only supported for json backends"
            )

        embed = discord.Embed(
            title="Have you backed up your current config?",
            description=f":warning: This will overwrite the current config, and you will lose existing settings! \
                \n :warning: You may also break the cog or bot, if the config is invalid. \
                \n To fix, make sure you can access the config file: \n `{path}`",
            color=await ctx.embed_color(),
        )
        confirmed, confirm = await confirm_pending(ctx, embed)
        if not confirmed:
            return

        with path.open("w") as f:
            json.dump(new_config, f, indent=4)

        await self._refresh_cached_guild_options()

        return await confirm.edit(
            embed=discord.Embed(
                title="Overwritten!",
                description="You will need to restart the bot for the changes to take effect.",
                color=await ctx.embed_color(),
            )
        )

    async def _refresh_cached_guild_options(self):
        """Reload in-memory state derived from config."""
        await self.services.ignore_regex_cache.load_all()
        await self.services.consent.load()

    @aiuserowner.group(name="prompt", invoke_without_command=True)
    async def global_prompt(self, ctx: commands.Context):
        """Show the global default prompt"""
        prompt = await self.config.custom_text_prompt()
        embed = discord.Embed(
            title="Global default prompt",
            description=truncate_prompt(prompt) if prompt else "Built-in default",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @global_prompt.command(name="set")
    async def global_prompt_set(self, ctx: commands.Context, *, prompt: Optional[str]):
        """Set the global default prompt from text or a text attachment"""
        if not prompt and ctx.message.attachments:
            if not ctx.message.attachments[0].filename.endswith(".txt"):
                return await ctx.send(
                    ":warning: Invalid attachment. Must be a `.txt` file."
                )
            prompt = (await ctx.message.attachments[0].read()).decode("utf-8")

        if not prompt:
            return await ctx.send("Provide a prompt or attach a `.txt` file.")

        await self.config.custom_text_prompt.set(prompt)

        embed = discord.Embed(
            title="The global prompt is now changed to:",
            description=f"{truncate_prompt(prompt)}",
            color=await ctx.embed_color(),
        )
        await add_prompt_metrics_fields(embed, self.services, ctx, prompt)
        return await ctx.send(embed=embed)

    @global_prompt.command(name="clear")
    async def global_prompt_clear(self, ctx: commands.Context):
        """Use the built-in global default prompt"""
        await self.config.custom_text_prompt.set(None)
        return await ctx.send("Global prompt reset to the built-in default.")

    async def _set_custom_endpoint(self, ctx: commands.Context, url: Optional[str]):
        if url == "codex":
            return await self._activate_codex_endpoint(ctx)

        if url == "openrouter":
            url = OPENROUTER_API_V1_URL
        elif url == "ollama":
            url = "http://localhost:11434/v1/"
        elif url in ["clear", "reset", "openai"]:
            url = None

        previous_url = await self.config.custom_openai_endpoint()
        await self._save_current_endpoint_models(previous_url)
        await self.config.custom_openai_endpoint.set(url)

        await ctx.message.add_reaction("🔄")
        self.services.openai_client = await setup_openai_client(self.bot, self.config)

        try:
            models = await self.services.openai_client.models.list()
        except AuthenticationError:
            logger.exception("Authentication failed for endpoint.")
            await self.config.custom_openai_endpoint.set(previous_url)
            self.services.openai_client = await setup_openai_client(
                self.bot, self.config
            )
            api_type = get_openai_compat_api_token_name(url)
            return await ctx.send(
                f":warning: Authentication failed for endpoint. "
                f"\nIf this endpoint requires an API key, please set it with "
                f"`{ctx.clean_prefix}set api {api_type} api_key,INSERT_API_KEY`"
            )
        except Exception:
            logger.exception("Invalid endpoint.")
            await self.config.custom_openai_endpoint.set(previous_url)
            self.services.openai_client = await setup_openai_client(
                self.bot, self.config
            )
            return await ctx.send(
                ":warning: Invalid endpoint. Please check logs for more information."
            )
        finally:
            await ctx.message.remove_reaction("🔄", ctx.me)

        endpoint_kind = get_openai_compat_kind(url)
        if endpoint_kind is CompatEndpointKind.OPENROUTER:
            chat_model = f"openai/{DEFAULT_LLM_MODEL}"
            image_model = f"openai/{DEFAULT_LLM_MODEL}"
        elif endpoint_kind is CompatEndpointKind.OPENAI:
            chat_model = DEFAULT_LLM_MODEL
            image_model = DEFAULT_LLM_MODEL
        else:
            chat_model = models.data[0].id
            image_model = models.data[0].id

        restored_count, guilds_with_parameters = await self._restore_endpoint_models(
            endpoint_url=url,
            chat_model=chat_model,
            image_model=image_model,
        )
        embed = await self._build_endpoint_update_embed(
            ctx=ctx,
            endpoint_url=url,
            chat_model=chat_model,
            image_model=image_model,
            restored_count=restored_count,
            guilds_with_parameters=guilds_with_parameters,
            include_third_party_footer=bool(url),
        )
        await ctx.send(embed=embed)

    async def _activate_codex_endpoint(self, ctx: commands.Context):
        if await is_codex_endpoint_mode(self.config):
            try:
                await ensure_valid_codex_oauth(self.config)
            except Exception:
                logger.warning("Existing Codex OAuth is not healthy", exc_info=True)
            else:
                if not await self._confirm_codex_reauth(ctx):
                    return

        await ctx.message.add_reaction("🔄")
        try:
            device_data = await start_device_authorization()
        except Exception:
            logger.exception("Failed to start Codex OAuth")
            await ctx.message.remove_reaction("🔄", ctx.me)
            return await ctx.send(
                ":warning: Failed to start Codex authentication. Please check logs."
            )

        embed = discord.Embed(
            title="Authenticate Codex endpoint",
            description=(
                f"Open {device_data['verification_url']} and enter this code:\n"
                f"`{device_data['user_code']}`"
            ),
            color=await ctx.embed_color(),
        )
        embed.add_field(
            name="",
            value="A follow-up message will be sent when authentication succeeds.",
            inline=False,
        )
        status_message = await ctx.send(embed=embed)

        try:
            tokens = await exchange_device_authorization(
                device_data["device_auth_id"],
                device_data["user_code"],
                device_data["interval"],
            )
        except TimeoutError:
            await ctx.message.remove_reaction("🔄", ctx.me)
            return await status_message.edit(
                embed=discord.Embed(
                    title=":warning: Codex authentication timed out",
                    color=await ctx.embed_color(),
                )
            )
        except Exception:
            logger.exception("Codex OAuth failed")
            await ctx.message.remove_reaction("🔄", ctx.me)
            return await ctx.send(
                embed=discord.Embed(
                    title=":warning: Codex authentication failed",
                    description="Please check logs for more information.",
                    color=await ctx.embed_color(),
                )
            )

        previous_url = await self.config.custom_openai_endpoint()
        await self._save_current_endpoint_models(previous_url)
        await set_codex_oauth(self.config, normalize_codex_tokens(tokens))
        oauth = await ensure_valid_codex_oauth(self.config)
        await set_codex_oauth(self.config, oauth)
        await self.config.custom_openai_endpoint.set(CODEX_ENDPOINT_MODE)
        self.services.openai_client = await setup_openai_client(self.bot, self.config)
        restored_count, guilds_with_parameters = await self._restore_endpoint_models(
            endpoint_url=CODEX_ENDPOINT_MODE,
            chat_model=CODEX_DEFAULT_MODEL,
            image_model=CODEX_DEFAULT_MODEL,
        )
        await ctx.message.remove_reaction("🔄", ctx.me)

        complete = await self._build_endpoint_update_embed(
            ctx=ctx,
            endpoint_url=CODEX_ENDPOINT_MODE,
            chat_model=CODEX_DEFAULT_MODEL,
            image_model=CODEX_DEFAULT_MODEL,
            restored_count=restored_count,
            guilds_with_parameters=guilds_with_parameters,
        )
        await ctx.send(embed=complete)

    async def _build_endpoint_update_embed(
        self,
        ctx: commands.Context,
        endpoint_url: Optional[str],
        chat_model: str,
        image_model: str,
        restored_count: int,
        guilds_with_parameters: list[str],
        *,
        include_third_party_footer: bool = False,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="Bot Custom OpenAI endpoint",
            color=await ctx.embed_color(),
        )
        if restored_count > 0:
            total_guilds = len(await self.config.all_guilds())
            value = (
                "Restored previously set models on this endpoint for "
                f"{restored_count} servers."
            )
            if restored_count < total_guilds:
                value += (
                    f"\nA further {total_guilds - restored_count} servers were set to "
                    f"`{chat_model}` for chat, and `{image_model}` for scanning images."
                )
            embed.add_field(
                name="🔄 Restored",
                value=value,
                inline=False,
            )
        else:
            embed.add_field(
                name="🔄 Reset",
                value=f"All per-server models have been set to use `{chat_model}` for chat and `{image_model}` for scanning images.",
                inline=False,
            )

        if guilds_with_parameters:
            embed.add_field(
                name=":warning: Caution",
                value=f"Custom parameters have been set in the following servers: `{', '.join(guilds_with_parameters)}`\nThey may not work with the new endpoint!",
                inline=False,
            )

        if endpoint_url:
            if endpoint_url == CODEX_ENDPOINT_MODE:
                embed.description = "Endpoint set to official OpenAI Codex endpoint."
            else:
                embed.description = f"Endpoint set to {endpoint_url}."
            if include_third_party_footer:
                embed.set_footer(
                    text="❗ Third party models may have undesirable results with this cog."
                )
        else:
            embed.description = "Endpoint reset back to official OpenAI endpoint."
        return embed

    def _endpoint_history_key(self, endpoint_url: Optional[str]) -> str:
        if endpoint_url == CODEX_ENDPOINT_MODE:
            return CODEX_ENDPOINT_MODE
        if not endpoint_url:
            return "default"
        return endpoint_url or "default"

    async def _save_current_endpoint_models(self, endpoint_url: Optional[str]):
        history = await self.config.endpoint_model_history()
        key = self._endpoint_history_key(endpoint_url)
        history[key] = {}
        for guild_id in await self.config.all_guilds():
            guild_config = self.config.guild_from_id(guild_id)
            history[key][str(guild_id)] = {
                "chat_model": await guild_config.model(),
                "image_model": await guild_config.scan_images_model(),
            }
        await self.config.endpoint_model_history.set(history)

    async def _restore_endpoint_models(
        self,
        endpoint_url: Optional[str],
        chat_model: str,
        image_model: str,
    ) -> tuple[int, list[str]]:
        history = await self.config.endpoint_model_history()
        saved_models = history.get(self._endpoint_history_key(endpoint_url), {})

        restored_count = 0
        guilds_with_parameters = []
        for guild_id in await self.config.all_guilds():
            guild_config = self.config.guild_from_id(guild_id)
            if str(guild_id) in saved_models:
                await guild_config.model.set(saved_models[str(guild_id)]["chat_model"])
                await guild_config.scan_images_model.set(
                    saved_models[str(guild_id)]["image_model"]
                )
                restored_count += 1
            else:
                await guild_config.model.set(chat_model)
                await guild_config.scan_images_model.set(image_model)

            if await guild_config.parameters():
                guild = self.bot.get_guild(guild_id)
                if guild:
                    guilds_with_parameters.append(str(guild.name))

        return restored_count, guilds_with_parameters

    async def _confirm_codex_reauth(self, ctx: commands.Context) -> bool:
        embed = discord.Embed(
            title="Codex is already active",
            description="Re-authenticate the active Codex endpoint?",
            color=await ctx.embed_color(),
        )

        confirmed, _ = await confirm_pending(ctx, embed)
        return confirmed
