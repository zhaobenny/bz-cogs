from __future__ import annotations

import json
import logging
from enum import Enum, auto
from io import BytesIO
from pathlib import Path
from typing import Optional

import discord
from openai import AuthenticationError
from redbot.core import checks, commands
from redbot.core.data_manager import cog_data_path

from aiuser.config.constants import OPENROUTER_API_V1_URL
from aiuser.config.defaults import DEFAULT_LLM_MODEL
from aiuser.providers.llm.codex.chatgpt import CODEX_ENDPOINT_MODE
from aiuser.providers.llm.openai_compatible.client import (
    get_openai_client,
    invalidate_openai_client,
)
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_api_token_name,
    get_openai_compat_kind,
)
from aiuser.providers.llm.registry import list_llm_models
from aiuser.settings.utilities import (
    add_prompt_metrics_fields,
    confirm_pending,
    truncate_prompt,
)
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


def _remove_codex_oauth(value):
    if isinstance(value, dict):
        value.pop("codex_oauth", None)
        for item in value.values():
            _remove_codex_oauth(item)
    elif isinstance(value, list):
        for item in value:
            _remove_codex_oauth(item)


class ChatGPTActivationPhase(Enum):
    IDLE = auto()
    CHOOSING_ACCOUNT = auto()
    CHECKING_ACCOUNT = auto()
    SIGNING_IN = auto()
    APPLYING = auto()


class OwnerSettings(MixinMeta):
    @commands.group(aliases=["ai_userowner"])
    @checks.is_owner()
    async def aiuserowner(self, _):
        """For some settings that apply bot-wide."""

    @aiuserowner.group(
        name="default_model", aliases=["defaultmodel"], invoke_without_command=True
    )
    async def default_model(self, ctx: commands.Context):
        """Show the bot-wide default chat model.

        Servers use this default unless they have their own model set.

        - `aiuser model list`: List available models.
        - `aiuserowner default_model set <model>`: Set the bot-wide default.
        - `aiuserowner default_model clear`: Restore the built-in default.
        """
        model = await self.config.default_model()
        embed = discord.Embed(
            title="Default chat model:",
            description=model,
            color=await ctx.embed_color(),
        )
        embed.set_footer(text="Used by servers without their own model setting")
        return await ctx.send(embed=embed)

    @default_model.command(name="set")
    async def default_model_set(self, ctx: commands.Context, model: str):
        """Set the default chat model for servers without their own setting"""
        async with ctx.typing():
            models = await list_llm_models(self.services)
        if model not in models:
            await ctx.send(":warning: Not a valid model!")
            return await self._paginate_models(ctx, models, query=model)

        await self.config.default_model.set(model)
        self.services.context_cache.clear()
        embed = discord.Embed(
            title="Default chat model is now set to:",
            description=model,
            color=await ctx.embed_color(),
        )
        embed.set_footer(text="Servers with their own model setting are unaffected")
        return await ctx.send(embed=embed)

    @default_model.command(name="clear", aliases=["reset"])
    async def default_model_clear(self, ctx: commands.Context):
        """Restore the built-in default chat model"""
        await self.config.default_model.clear()
        self.services.context_cache.clear()
        model = await self.config.default_model()
        embed = discord.Embed(
            title="Default chat model reset to:",
            description=model,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

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
        display_url = "ChatGPT" if url == CODEX_ENDPOINT_MODE else (url or "OpenAI")
        return await ctx.maybe_send_embed(f"Model endpoint: `{display_url}`")

    @endpoint.command(name="set")
    async def endpoint_set(self, ctx: commands.Context, url: str):
        """Set an endpoint URL or a built-in endpoint name.

        Use `chatgpt` for a ChatGPT plan, `openrouter` or `ollama` for
        those providers, or `openai` for the API route.
        """
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
        await invalidate_openai_client(self.services)

        return await ctx.send(f"Endpoint request timeout set to `{seconds}` seconds.")

    @aiuserowner.group(name="config")
    async def owner_config(self, _):
        """Import or export the complete cog configuration"""

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

        try:
            exported = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to read AIUser config for export")
            return await ctx.send(":warning: Failed to read the current config")

        _remove_codex_oauth(exported)
        payload = BytesIO(json.dumps(exported, indent=4).encode("utf-8"))
        await ctx.send(file=discord.File(payload, filename="aiuser_config.json"))
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

        _remove_codex_oauth(new_config)

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

        with path.open("w") as f:  # noqa: ASYNC230 - small local config export
            json.dump(new_config, f, indent=4)
        path.chmod(0o600)

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
    async def global_prompt_set(
        self,
        ctx: commands.Context,
        *,
        prompt: Optional[str],  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
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

    async def _set_custom_endpoint(self, ctx: commands.Context, url: str | None):
        if url in {"chatgpt", "codex", "codex-new"}:
            return await self._activate_codex_endpoint(
                ctx, new_account=url == "codex-new"
            )

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
        await invalidate_openai_client(self.services)
        client = await get_openai_client(self.services)
        if client is None:
            await self.config.custom_openai_endpoint.set(previous_url)
            await ctx.message.remove_reaction("🔄", ctx.me)
            api_type = get_openai_compat_api_token_name(url)
            return await ctx.send(
                f":warning: No API key set for this endpoint. "
                f"\nPlease set it with "
                f"`{ctx.clean_prefix}set api {api_type} api_key,INSERT_API_KEY`"
            )

        try:
            models = await client.models.list()
        except AuthenticationError:
            logger.exception("Authentication failed for endpoint.")
            await self.config.custom_openai_endpoint.set(previous_url)
            await invalidate_openai_client(self.services)
            api_type = get_openai_compat_api_token_name(url)
            return await ctx.send(
                f":warning: Authentication failed for endpoint. "
                f"\nIf this endpoint requires an API key, please set it with "
                f"`{ctx.clean_prefix}set api {api_type} api_key,INSERT_API_KEY`"
            )
        except Exception:
            logger.exception("Invalid endpoint.")
            await self.config.custom_openai_endpoint.set(previous_url)
            await invalidate_openai_client(self.services)
            return await ctx.send(
                ":warning: Invalid endpoint. Please check logs for more information."
            )
        finally:
            await ctx.message.remove_reaction("🔄", ctx.me)

        if previous_url != url:
            self.services.context_cache.clear()

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

    async def _activate_codex_endpoint(
        self, ctx: commands.Context, new_account: bool = False
    ):
        if (
            getattr(self, "_chatgpt_activation_phase", ChatGPTActivationPhase.IDLE)
            is not ChatGPTActivationPhase.IDLE
        ):
            return await ctx.send("ChatGPT setup is already in progress.")
        self._chatgpt_activation_phase = ChatGPTActivationPhase.CHOOSING_ACCOUNT
        try:
            return await self._run_codex_activation(ctx, new_account)
        finally:
            self._chatgpt_activation_phase = ChatGPTActivationPhase.IDLE

    async def _run_codex_activation(self, ctx: commands.Context, new_account: bool):
        from aiuser.providers.llm.codex.chatgpt import SignInPhase, finish, load, start
        from aiuser.providers.llm.codex.view import (
            AccountChoice,
            ChatGPTAccountView,
            ChatGPTLoginView,
        )

        saved = await load(self.bot)
        if saved.get("client_id") and not new_account:
            account_view = ChatGPTAccountView(self.bot, ctx.author.id)
            email = saved.get("email") or ""
            local, separator, domain = email.partition("@")
            account = (
                f"{local[:1]}•••@{domain}"
                if local and separator and domain
                else "a ChatGPT account"
            )
            account_message = await ctx.send(
                embed=discord.Embed(
                    title="Connect ChatGPT",
                    description=f"Connected as **{discord.utils.escape_markdown(account)}**. Choose an account to use.",
                    color=await ctx.embed_color(),
                ),
                view=account_view,
            )
            await account_view.wait()
            await account_message.edit(view=None)
            if account_view.choice in (AccountChoice.WAITING, AccountChoice.EXPIRED):
                return
            new_account = account_view.choice is AccountChoice.SWITCH

        self._chatgpt_activation_phase = ChatGPTActivationPhase.CHECKING_ACCOUNT
        models = None
        if not new_account:
            try:
                models = (
                    await list_llm_models(self.services)
                    if await self.config.custom_openai_endpoint() == CODEX_ENDPOINT_MODE
                    else None
                )
                if models is None:
                    from aiuser.providers.llm.codex.provider import CodexProvider

                    models = await CodexProvider(self.config, self.bot).list_models()
            except Exception as exc:  # noqa: BLE001 - do not expose authentication errors
                logger.info("Saved ChatGPT login unavailable (%s)", type(exc).__name__)
        if not models:
            self._chatgpt_activation_phase = ChatGPTActivationPhase.SIGNING_IN
            url, pending = await start(self.bot, new_account=new_account)
            view = ChatGPTLoginView(self.bot, ctx.author.id)
            message = await ctx.send(
                embed=discord.Embed(
                    title="Sign in with ChatGPT",
                    description=(
                        f"[Open ChatGPT sign-in]({url})\n\n"
                        "After signing in, copy the full URL from your browser's address bar "
                        "and select **Paste callback URL** below. "
                        "Your browser may say it cannot connect - that's expected."
                    ),
                    color=await ctx.embed_color(),
                ).set_footer(
                    text="Paste the URL only into the private form, never in a channel."
                ),
                view=view,
            )
            try:
                await view.wait()
                if view.result.cancelled() or not view.result.done():
                    pending.phase = SignInPhase.EXPIRED
                    return await message.edit(
                        content="ChatGPT sign-in timed out.", embed=None, view=None
                    )
                callback, interaction = view.result.result()
                try:
                    models = await finish(self.bot, pending, callback)
                except Exception as exc:  # noqa: BLE001 - callbacks can contain secrets
                    logger.warning("ChatGPT sign-in failed (%s)", type(exc).__name__)
                    await interaction.followup.send(
                        "ChatGPT sign-in failed. Start again and check the bot logs for the error type.",
                        ephemeral=True,
                    )
                    return await message.edit(
                        content="ChatGPT sign-in failed.", embed=None, view=None
                    )
                await interaction.followup.send(
                    "ChatGPT sign-in succeeded.", ephemeral=True
                )
                await message.edit(
                    content="ChatGPT sign-in completed.", embed=None, view=None
                )
            finally:
                if pending.phase is SignInPhase.WAITING:
                    pending.phase = SignInPhase.CANCELLED
                view.stop()
        self._chatgpt_activation_phase = ChatGPTActivationPhase.APPLYING
        selected_model = models[0]
        previous_url = await self.config.custom_openai_endpoint()
        await self._save_current_endpoint_models(previous_url)
        history = await self.config.endpoint_model_history()
        saved_models = history.get(self._endpoint_history_key(CODEX_ENDPOINT_MODE), {})
        if saved_models.get("__default_model__") not in models:
            saved_models.pop("__default_model__", None)
        for key, value in list(saved_models.items()):
            if key == "__default_model__":
                continue
            if value.get("chat_model") and value["chat_model"] not in models:
                value["chat_model"] = None
            if value.get("image_model") and value["image_model"] not in models:
                value["image_model"] = selected_model
        await self.config.endpoint_model_history.set(history)
        await self.config.custom_openai_endpoint.set(CODEX_ENDPOINT_MODE)
        if previous_url != CODEX_ENDPOINT_MODE:
            self.services.context_cache.clear()
        await invalidate_openai_client(self.services)
        restored_count, guilds_with_parameters = await self._restore_endpoint_models(
            endpoint_url=CODEX_ENDPOINT_MODE,
            chat_model=selected_model,
            image_model=selected_model,
        )

        complete = await self._build_endpoint_update_embed(
            ctx=ctx,
            endpoint_url=CODEX_ENDPOINT_MODE,
            chat_model=selected_model,
            image_model=selected_model,
            restored_count=restored_count,
            guilds_with_parameters=guilds_with_parameters,
        )
        await ctx.send(embed=complete)

    async def _build_endpoint_update_embed(
        self,
        ctx: commands.Context,
        endpoint_url: str | None,
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
                    f"\nA further {total_guilds - restored_count} servers will use "
                    f"the default `{chat_model}` for chat and `{image_model}` for "
                    "scanning images."
                )
            embed.add_field(
                name="🔄 Restored",
                value=value,
                inline=False,
            )
        else:
            embed.add_field(
                name="🔄 Reset",
                value=(
                    "Servers without their own model setting will use the default "
                    f"`{chat_model}` for chat. All servers were set to `{image_model}` "
                    "for scanning images."
                ),
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
                embed.description = "Endpoint set to ChatGPT plan access."
            else:
                embed.description = f"Endpoint set to {endpoint_url}."
            if include_third_party_footer:
                embed.set_footer(
                    text="❗ Third party models may have undesirable results with this cog."
                )
        else:
            embed.description = "Endpoint reset back to official OpenAI endpoint."
        return embed

    def _endpoint_history_key(self, endpoint_url: str | None) -> str:
        if endpoint_url == CODEX_ENDPOINT_MODE:
            return CODEX_ENDPOINT_MODE
        if not endpoint_url:
            return "default"
        return endpoint_url or "default"

    async def _save_current_endpoint_models(self, endpoint_url: str | None):
        history = await self.config.endpoint_model_history()
        key = self._endpoint_history_key(endpoint_url)
        history[key] = {"__default_model__": await self.config.default_model()}
        for guild_id in await self.config.all_guilds():
            guild_config = self.config.guild_from_id(guild_id)
            history[key][str(guild_id)] = {
                "chat_model": await guild_config.model(default=None),
                "image_model": await guild_config.scan_images_model(),
            }
        await self.config.endpoint_model_history.set(history)

    async def _restore_endpoint_models(
        self,
        endpoint_url: str | None,
        chat_model: str,
        image_model: str,
    ) -> tuple[int, list[str]]:
        history = await self.config.endpoint_model_history()
        saved_models = history.get(self._endpoint_history_key(endpoint_url), {})
        chat_model = saved_models.get("__default_model__", chat_model)
        await self.config.default_model.set(chat_model)

        restored_count = 0
        guilds_with_parameters = []
        for guild_id in await self.config.all_guilds():
            guild_config = self.config.guild_from_id(guild_id)
            if str(guild_id) in saved_models:
                saved_chat_model = saved_models[str(guild_id)]["chat_model"]
                if saved_chat_model is None:
                    await guild_config.model.clear()
                else:
                    await guild_config.model.set(saved_chat_model)
                await guild_config.scan_images_model.set(
                    saved_models[str(guild_id)]["image_model"]
                )
                restored_count += 1
            else:
                await guild_config.model.clear()
                await guild_config.scan_images_model.set(image_model)

            if await guild_config.parameters():
                guild = self.bot.get_guild(guild_id)
                if guild:
                    guilds_with_parameters.append(str(guild.name))

        return restored_count, guilds_with_parameters
