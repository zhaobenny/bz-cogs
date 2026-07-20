import json
import logging
from datetime import timedelta
from typing import Optional, Union

import discord
from redbot.core import checks, commands
from redbot.core.utils.menus import SimpleMenu

from aiuser.config.constants import CHANNEL_MENTION_OR_ID_PATTERN
from aiuser.config.defaults import DEFAULT_STT_PROVIDER
from aiuser.config.model_info import get_model_info
from aiuser.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)
from aiuser.llm.registry import list_llm_models
from aiuser.settings.functions.base import FunctionCallingSettings
from aiuser.settings.history import HistorySettings
from aiuser.settings.media import MediaSettings
from aiuser.settings.memory import MemorySettings
from aiuser.settings.owner import OwnerSettings
from aiuser.settings.prompt import PromptSettings
from aiuser.settings.random_message import RandomMessageSettings
from aiuser.settings.reply import ReplySettings
from aiuser.settings.response import ResponseSettings
from aiuser.settings.triggers import TriggerSettings
from aiuser.settings.utilities import rank_choices_for_query
from aiuser.speech.stt import DEFAULT_MODELS as STT_DEFAULT_MODELS
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
    RandomMessageSettings,
    FunctionCallingSettings,
    MemorySettings,
    MixinMeta,
):
    @commands.group(aliases=["ai_user"])
    @commands.bot_has_permissions(embed_links=True, add_reactions=True)
    @commands.guild_only()
    async def aiuser(self, _):
        """Configure replies to messages and images in enabled reply channels"""
        pass

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

        self.services.override_prompt_start_time[ctx.guild.id] = (
            ctx.message.created_at - timedelta(seconds=1)
        )
        await ctx.react_quietly("✅")

    @aiuser.command(aliases=["config", "settings", "showsettings"])
    async def status(self, ctx: commands.Context):
        """Returns current settings

        (Current config per server)
        """
        config = await self.config.guild(ctx.guild).get_raw()
        glob_config = await self.config.get_raw()
        whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        channels = [f"<#{channel_id}>" for channel_id in whitelist]
        embeds = []

        main_embed = discord.Embed(
            title="AI User Settings", color=await ctx.embed_color()
        )
        main_embed.add_field(name="Version", inline=True, value=f"`{self.__version__}`")

        main_embed.add_field(name="Model", inline=True, value=f"`{config['model']}`")
        main_embed.add_field(
            name="Server Reply Chance",
            inline=True,
            value=f"`{config['reply_percent'] * 100:.2f}`%",
        )

        main_embed.add_field(
            name="Opt In By Default",
            inline=True,
            value=f"`{config['optin_by_default']}`",
        )

        main_embed.add_field(
            name="Always Reply to Mentions/Replies",
            inline=True,
            value=f"`{config['reply_to_mentions_replies']}`",
        )
        main_embed.add_field(
            name="Context Message Limit",
            inline=True,
            value=f"`{config['messages_backread']}` messages",
        )
        main_embed.add_field(
            name="Context Message Gap",
            inline=True,
            value=f"`{config['messages_backread_seconds']}` seconds",
        )

        compaction_enabled = config.get("compaction_enabled", False)
        main_embed.add_field(
            name="Context Compaction",
            inline=True,
            value="`Enabled`" if compaction_enabled else "`Disabled`",
        )

        main_embed.add_field(
            name="Reply Channels",
            inline=True,
            value=" ".join(channels) if channels else "`None`",
        )

        endpoint_url = str(glob_config["custom_openai_endpoint"] or "")
        if endpoint_url == "codex":
            endpoint_text = "Using [OpenAI](https://openai.com/) via Codex"
        elif get_openai_compat_kind(endpoint_url) is CompatEndpointKind.OPENROUTER:
            endpoint_text = "Using [OpenRouter](https://openrouter.ai) endpoint"
        elif endpoint_url:
            endpoint_text = "Using a custom endpoint"
        else:
            endpoint_text = "Using [OpenAI](https://openai.com/)"
        main_embed.add_field(name="LLM Endpoint", inline=True, value=endpoint_text)

        main_embed.add_field(
            name="",
            inline=False,
            value="",
        )

        main_embed.add_field(
            name="Memory Retrieval",
            inline=True,
            value="Enabled" if config["query_memories"] else "Disabled",
        )

        main_embed.add_field(
            name="Tools",
            inline=True,
            value="Enabled" if config["function_calling"] else "Disabled",
        )
        main_embed.add_field(
            name="Random Messages",
            inline=True,
            value=(
                f"Enabled: `{config['random_messages_percent'] * 100:.2f}`% every `33` min"
                if config["random_messages_enabled"]
                else "Disabled"
            ),
        )

        media_embed = discord.Embed(
            title="Media Settings", color=await ctx.embed_color()
        )
        media_embed.add_field(
            name="Image Processing",
            inline=True,
            value="Enabled" if config["scan_images"] else "Disabled",
        )
        if config["scan_images"]:
            media_embed.add_field(
                name="Maximum Image Size",
                inline=True,
                value=f"`{config['max_image_size'] / 1024 / 1024:.2f}` MB",
            )
            media_embed.add_field(
                name="Image Detail",
                inline=True,
                value=f"`{config['scan_images_detail']}`",
            )
            media_embed.add_field(
                name="Image Model",
                inline=True,
                value=f"`{config['scan_images_model'] or 'Chat model'}`",
            )
        media_embed.add_field(
            name="Audio Transcription",
            inline=True,
            value="Enabled" if config["scan_audio"] else "Disabled",
        )
        if config["scan_audio"]:
            stt_provider = (
                config["scan_audio_provider"] or DEFAULT_STT_PROVIDER
            ).lower()
            media_embed.add_field(
                name="Audio Provider",
                inline=True,
                value=f"`{stt_provider}`",
            )
            media_embed.add_field(
                name="Maximum Audio Duration",
                inline=True,
                value=f"`{config['max_audio_duration']}` seconds",
            )
            stt_model = config["scan_audio_model"] or STT_DEFAULT_MODELS.get(
                stt_provider
            )
            media_embed.add_field(
                name="Audio Model",
                inline=True,
                value=f"`{stt_model}`",
            )

        whitelisted_trigger = bool(
            config["members_whitelist"] or config["roles_whitelist"]
        )

        main_embed.add_field(
            name="Trigger Allowlist Active",
            inline=True,
            value=f"`{whitelisted_trigger}`",
        )

        main_embed.add_field(
            name="Allowed Members",
            inline=True,
            value=" ".join(
                [f"<@{member_id}>" for member_id in config["members_whitelist"]]
            )
            or "`None`",
        )

        main_embed.add_field(
            name="Allowed Roles",
            inline=True,
            value=" ".join([f"<@&{role_id}>" for role_id in config["roles_whitelist"]])
            or "`None`",
        )

        removelist_regexes = config["removelist_regexes"]
        regexes_num = 0
        if removelist_regexes is not None:
            regexes_num = len(removelist_regexes)
        main_embed.add_field(
            name="Response Filters", value=f"`{regexes_num}` regexes set"
        )
        main_embed.add_field(name="Ignore Regex", value=f"`{config['ignore_regex']}`")
        main_embed.add_field(
            name="Public Forget Command",
            inline=True,
            value=f"`{config['public_forget']}`",
        )
        embeds.append(main_embed)
        embeds.append(media_embed)

        parameters = config["parameters"]
        if parameters is not None:
            parameters = json.loads(parameters)
            parameters_embed = discord.Embed(
                title="Custom Parameters to Endpoint", color=await ctx.embed_color()
            )
            for key, value in parameters.items():
                parameters_embed.add_field(
                    name=key, value=f"```{json.dumps(value, indent=4)}```", inline=False
                )
            embeds.append(parameters_embed)

        for embed in embeds:
            await ctx.send(embed=embed)
        return

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def channels(self, _):
        """Manage enabled reply channels"""
        pass

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
            return await ctx.send("Invalid channel")
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel.id in new_whitelist:
            return await ctx.send("Replies are already enabled in that channel.")
        new_whitelist.append(channel.id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        return await self._send_channel_whitelist(ctx, new_whitelist)

    @channels.command(name="remove")
    async def channels_remove(
        self,
        ctx: commands.Context,
        channel: Union[COMPATIBLE_CHANNELS, str],
    ):
        """Disable replies in a channel

        **Arguments**
            - `channel` A mention or ID of the channel
        """
        if isinstance(channel, str):
            match = CHANNEL_MENTION_OR_ID_PATTERN.fullmatch(channel.strip())
            if not match:
                return await ctx.send(
                    "Invalid channel. Provide a channel mention or ID."
                )
            channel_id = int(match.group(1) or match.group(2))
        else:
            channel_id = channel.id
        new_whitelist = await self.config.guild(ctx.guild).channels_whitelist()
        if channel_id not in new_whitelist:
            return await ctx.send("Replies are not enabled in that channel.")
        new_whitelist.remove(channel_id)
        await self.config.guild(ctx.guild).channels_whitelist.set(new_whitelist)
        return await self._send_channel_whitelist(ctx, new_whitelist)

    async def _send_channel_whitelist(self, ctx: commands.Context, whitelist):
        embed = discord.Embed(
            title="Enabled reply channels:", color=await ctx.embed_color()
        )
        channels = [f"<#{channel_id}>" for channel_id in whitelist]
        embed.description = "\n".join(channels) if channels else "None"
        return await ctx.send(embed=embed)

    @aiuser.group(invoke_without_command=True)
    @checks.is_owner()
    async def model(self, ctx: commands.Context):
        """Show the current chat completion model"""
        model = await self.config.guild(ctx.guild).model()
        return await ctx.maybe_send_embed(f"This server's chat model is: `{model}`")

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
            await ctx.send(":warning: Not a valid model!")
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

    async def _paginate_models(self, ctx, models, query: Optional[str] = None):
        if not models:
            return await ctx.send(":warning: No models are currently available.")

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
        if not await self.consent.opt_in(ctx.author.id):
            return await ctx.send("You are already opted in.")
        await ctx.send("You are now opted in bot-wide")

    @aiuser.command()
    async def optout(self, ctx: commands.Context):
        """Opt out of sending your messages / images to OpenAI or another endpoint (bot-wide)

        This will prevent the bot from replying to your messages or using your messages.
        """
        if not await self.consent.opt_out(ctx.author.id):
            return await ctx.send("You are already opted out.")
        await ctx.send("You are now opted out bot-wide")

    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def consent(self, _):
        """Configure server-wide consent defaults"""
        pass

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
            return await ctx.send(
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
