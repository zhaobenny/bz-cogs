from __future__ import annotations

import logging
from typing import Union

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aiuser.config.constants import CHANNEL_MENTION_OR_ID_PATTERN
from aiuser.config.model_info import get_model_info
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)
from aiuser.providers.llm.registry import list_llm_models
from aiuser.settings.functions.base import FunctionCallingSettings
from aiuser.settings.history import HistorySettings
from aiuser.settings.mcp import MCPSettings
from aiuser.settings.media import MediaSettings
from aiuser.settings.memory import MemorySettings
from aiuser.settings.onboarding import OnboardingView, ProviderState
from aiuser.settings.owner import OwnerSettings
from aiuser.settings.prompt import PromptSettings
from aiuser.settings.random_message import RandomMessageSettings
from aiuser.settings.reply import ReplySettings
from aiuser.settings.response import ResponseSettings
from aiuser.settings.status import build_status_embed
from aiuser.settings.triggers import TriggerSettings
from aiuser.settings.utilities import rank_choices_for_query
from aiuser.types.abc import MixinMeta
from aiuser.types.types import COMPATIBLE_CHANNELS

logger = logging.getLogger("red.bz_cogs.aiuser")


class Settings(
    PromptSettings,
    MediaSettings,
    HistorySettings,
    ReplySettings,
    ResponseSettings,
    TriggerSettings,
    OwnerSettings,
    MCPSettings,
    RandomMessageSettings,
    FunctionCallingSettings,
    MemorySettings,
    MixinMeta,
):
    @commands.group(
        help_override="Configure replies to messages and images in enabled reply channels",
        aliases=["ai_user"],
    )
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.guild_only()
    async def aiuser(self, _):
        pass

    @aiuser.command(
        help="Guide the bot owner through setup for this server.", name="setup"
    )
    @checks.is_owner()
    async def setup_wizard(self, ctx: commands.Context):
        if self.services is None:
            return await ctx.maybe_send_embed(
                "AI User is still loading. Try again shortly."
            )
        settings = await self.config.guild(ctx.guild).all()
        settings["global_prompt"] = await self.config.custom_text_prompt()
        settings["default_model"] = await self.config.default_model()
        dm_prefixes = await self.bot.get_valid_prefixes()
        settings["dm_prefix"] = dm_prefixes[0] if dm_prefixes else "[p]"
        view = OnboardingView(self, ctx, settings, False)
        for channel_id in settings.get("channels_whitelist", []):
            channel = ctx.guild.get_channel(channel_id)
            if channel is None or channel.type not in {
                discord.ChannelType.text,
                discord.ChannelType.news,
            }:
                continue
            permissions = channel.permissions_for(ctx.guild.me)
            if (
                permissions.view_channel
                and permissions.send_messages
                and permissions.read_message_history
            ):
                view.channel = channel
                if hasattr(view.choose_channel, "default_values"):
                    view.choose_channel.default_values = [discord.Object(id=channel.id)]
                break
        configured = await view.check_provider()
        endpoint = view.settings.get("endpoint")
        active = (
            "codex" if endpoint == "codex" else get_openai_compat_kind(endpoint).value
        )
        view.provider_choice = (
            active
            if active in {"openai", "openrouter", "codex", "custom"}
            else "openai"
        )
        view.provider_state = (
            ProviderState.CHECKING if configured else ProviderState.UNCONFIGURED
        )
        view.update_items()
        view.message = await ctx.send(**view.display())
        if view.provider_state is ProviderState.CHECKING:
            await view.verify_existing_provider()
            if not view.is_finished():
                view.update_items()
                try:
                    await view.message.edit(**view.display())
                except discord.HTTPException:
                    view.stop()

    @aiuser.command(aliases=["lobotomize"])
    async def forget(self, ctx: commands.Context):
        """Forces the bot to forget the current conversation up to this point

        This is useful if the LLM is stuck doing unwanted behaviour or giving undesirable results.
        See `[p]aiuser triggers public_forget` to allow non-admins to use this command.
        """
        if (
            not ctx.channel.permissions_for(ctx.author).manage_messages
            and not await self.config.guild(ctx.guild).public_forget()
        ):
            return await ctx.react_quietly("❌")

        self.services.override_prompt_start_time[ctx.guild.id] = ctx.message.created_at
        await ctx.react_quietly("✅")

    @aiuser.command(aliases=["config", "settings", "showsettings"])
    async def status(self, ctx: commands.Context):
        """Returns current settings

        (Current config per server)
        """
        config = await self.config.guild(ctx.guild).get_raw()
        glob_config = await self.config.get_raw()
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        default_model = await self.config.default_model()
        embed = await build_status_embed(
            ctx=ctx,
            services=self.services,
            version=self.__version__,
            config=config,
            glob_config=glob_config,
            default_model=default_model,
            whitelist=whitelist,
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def channels(self, _):
        """Manage enabled reply channels"""

    @channels.command(name="list")
    async def channels_list(self, ctx: commands.Context):
        """List enabled reply channels"""
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        return await self._send_channel_whitelist(ctx, whitelist)

    @channels.command(name="add")
    @checks.is_owner()
    async def channels_add(
        self,
        ctx: commands.Context,
        channel: COMPATIBLE_CHANNELS,
    ):
        """Enable replies in a channel

        **Arguments**
            - `channel` A mention of the channel
        """
        if not channel:
            return await ctx.maybe_send_embed("Invalid channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.maybe_send_embed(
                "Replies are already enabled in that channel."
            )
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        return await self._send_channel_whitelist(ctx, new_whitelist)

    @channels.command(name="remove")
    async def channels_remove(
        self,
        ctx: commands.Context,
        channel: Union[COMPATIBLE_CHANNELS, str],  # noqa: UP007 - Red command converter requires typing.Union on Python 3.9
    ):
        """Disable replies in a channel

        **Arguments**
            - `channel` A mention or ID of the channel
        """
        if isinstance(channel, str):
            match = CHANNEL_MENTION_OR_ID_PATTERN.fullmatch(channel.strip())
            if not match:
                return await ctx.maybe_send_embed(
                    "Invalid channel. Provide a channel mention or ID."
                )
            channel_id = int(match.group(1) or match.group(2))
        else:
            channel_id = channel.id
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel_id not in new_whitelist:
            return await ctx.maybe_send_embed(
                "Replies are not enabled in that channel."
            )
        new_whitelist.remove(channel_id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        return await self._send_channel_whitelist(ctx, new_whitelist)

    async def _send_channel_whitelist(self, ctx: commands.Context, whitelist):
        embed = discord.Embed(
            title="Enabled reply channels:", color=await ctx.embed_color()
        )
        channels = [
            channel.mention
            if (channel := ctx.guild.get_channel_or_thread(channel_id))
            else f"Unknown channel (`{channel_id}`)"
            for channel_id in whitelist
        ]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.group(invoke_without_command=True)
    @checks.is_owner()
    async def model(self, ctx: commands.Context):
        """Show this server's chat model.

        - `aiuser model list`: List available models.
        - `aiuser model set <model>`: Set this server's model.
        - `aiuser model clear`: Use the bot-wide default.
        - `aiuserowner default_model set <model>`: Change the bot-wide default.
        """
        server_model = await self.config.guild(ctx.guild).model()
        model = server_model or await self.config.default_model()
        embed = discord.Embed(
            title="This server's chat model:",
            description=model,
            color=await ctx.embed_color(),
        )
        if not server_model:
            embed.set_footer(text="Using the bot-wide default")
        return await ctx.send(embed=embed)

    @model.command(name="list")
    async def model_list(self, ctx: commands.Context):
        """List available chat completion models"""
        async with ctx.typing():
            models = await list_llm_models(self.services)
        return await self._paginate_models(ctx, models)

    @model.command(name="set")
    async def model_set(self, ctx: commands.Context, model: str):
        """Change the chat completion model

        **Arguments**
            - `model` The model to use eg. `gpt-4`
        """
        async with ctx.typing():
            models = await list_llm_models(self.services)

        if model not in models:
            await ctx.maybe_send_embed(":warning: Not a valid model!")
            return await self._paginate_models(ctx, models, query=model)

        await self.config.guild(ctx.guild).model.set(model)
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=model,
            color=await ctx.embed_color(),
        )

        if (
            await self.config.guild(ctx.guild).function_calling()
            and not get_model_info(model).supports_tools
        ):
            embed.set_footer(
                text="⚠️ Tool use is enabled - ensure the selected model supports tools"
            )

        return await ctx.send(embed=embed)

    @model.command(name="clear", aliases=["reset"])
    async def model_clear(self, ctx: commands.Context):
        """Use the bot-wide default chat model"""
        await self.config.guild(ctx.guild).model.clear()
        model = await self.config.default_model()
        embed = discord.Embed(
            title="This server's chat model is now set to:",
            description=model,
            color=await ctx.embed_color(),
        )
        embed.set_footer(text="Using the bot-wide default")
        return await ctx.send(embed=embed)

    async def _paginate_models(self, ctx, models, query: str | None = None):
        if not models:
            return await ctx.maybe_send_embed(
                ":warning: No models are currently available."
            )

        if query:
            models = rank_choices_for_query(models, query)

        pagified_models = [models[i : i + 10] for i in range(0, len(models), 10)]
        menu_pages = []

        for models_page in pagified_models:
            embed = discord.Embed(
                title=("Available Models"),
                color=await ctx.embed_color(),
            )
            embed.description = "\n".join([f"`{model}`" for model in models_page])
            menu_pages.append(embed)

        endpoint_kind = get_openai_compat_kind(
            await self.config.custom_openai_endpoint()
        )
        if endpoint_kind is CompatEndpointKind.OPENROUTER:
            menu_pages[0].add_field(
                name="For pricing and more details go to:",
                value="https://openrouter.ai/models",
                inline=False,
            )

        if len(menu_pages) == 1:
            return await ctx.send(embed=menu_pages[0])
        for i, page in enumerate(menu_pages):
            page.set_footer(text=f"Page {i + 1} of {len(menu_pages)}")
        return await SimpleMenu(menu_pages).start(ctx)

    @aiuser.command()
    async def optin(self, ctx: commands.Context):
        """Opt in of sending your messages / images to OpenAI or another endpoint (bot-wide)

        This will allow the bot to reply to your messages or use your messages.
        """
        if not await self.services.consent.opt_in(ctx.author.id):
            return await ctx.maybe_send_embed("You are already opted in.")
        await ctx.maybe_send_embed("You are now opted in bot-wide")

    @aiuser.command()
    async def optout(self, ctx: commands.Context):
        """Opt out of sending your messages / images to OpenAI or another endpoint (bot-wide)

        This will prevent the bot from replying to your messages or using your messages.
        """
        if not await self.services.consent.opt_out(ctx.author.id):
            return await ctx.maybe_send_embed("You are already opted out.")
        await ctx.maybe_send_embed("You are now opted out bot-wide")

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def consent(self, _):
        """Configure server-wide consent defaults"""

    @consent.group(name="default", invoke_without_command=True)
    async def consent_default(self, ctx: commands.Context):
        """Show whether server members are opted in by default"""
        value = await self.config.guild(ctx.guild).optin_by_default()
        return await ctx.maybe_send_embed(f"Users opted in by default: `{value}`")

    @consent_default.command(name="enable")
    async def consent_default_enable(self, ctx: commands.Context):
        """Opt server members in by default

        This command is disabled for servers with more than 150 members.
        """
        if len(ctx.guild.members) > 150:
            # if you STILL want to enable this for a server with more than 150 members
            # add the line below to the specific guild in the cog's settings.json:
            # "optin_by_default": true
            # insert concern about user privacy and getting user consent here
            return await ctx.maybe_send_embed(
                "You cannot enable this setting for servers with more than 150 members."
            )
        return await self._set_consent_default(ctx, True)

    @consent_default.command(name="disable")
    async def consent_default_disable(self, ctx: commands.Context):
        """Require server members to opt in individually"""
        return await self._set_consent_default(ctx, False)

    async def _set_consent_default(self, ctx: commands.Context, value: bool):
        await self.config.guild(ctx.guild).optin_by_default.set(value)
        embed = discord.Embed(
            title="Users are now opted in by default in this server:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @consent.group(name="warning", invoke_without_command=True)
    async def consent_warning(self, ctx: commands.Context):
        """Show whether the opt-in warning is enabled"""
        disabled = await self.config.guild(ctx.guild).optin_disable_embed()
        return await ctx.maybe_send_embed(f"Opt-in warning enabled: `{not disabled}`")

    @consent_warning.command(name="enable")
    async def consent_warning_enable(self, ctx: commands.Context):
        """Show the opt-in warning to users who have not chosen"""
        return await self._set_consent_warning(ctx, True)

    @consent_warning.command(name="disable")
    async def consent_warning_disable(self, ctx: commands.Context):
        """Stop showing the opt-in warning"""
        return await self._set_consent_warning(ctx, False)

    async def _set_consent_warning(self, ctx: commands.Context, enabled: bool):
        await self.config.guild(ctx.guild).optin_disable_embed.set(not enabled)
        embed = discord.Embed(
            title="Opt-in warning embed is now:",
            description="Enabled" if enabled else "Disabled",
            color=await ctx.embed_color(),
        )
        if not enabled:
            embed.add_field(
                name=":warning: Warning :warning:",
                value="Users not yet opt-in/out will be unaware their messages are not being processed",
                inline=False,
            )
        return await ctx.send(embed=embed)
