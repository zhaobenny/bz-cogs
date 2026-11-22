"""Read-only AIUser setup help for the bot owner in regular chat."""

from __future__ import annotations

import inspect
import json
from typing import Any

import discord
from redbot.core import commands

from aiuser.config.resolver import ScopedConfigResolver
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

_REPLY_SETTINGS = (
    "reply_percent",
    "reply_to_mentions_replies",
    "conversation_reply_percent",
    "conversation_reply_time",
    "messages_min_length",
)
_REPLY_COMMANDS = (
    "aiuser channels add",
    "aiuser channels remove",
    "aiuser reply chance set",
    "aiuser reply chance clear",
    "aiuser reply mentions enable",
    "aiuser reply mentions disable",
    "aiuser reply followup chance set",
    "aiuser reply minimum_length set",
    "aiuser random show",
)
_SETUP_COMMANDS = (
    "aiuser setup",
    "aiuser status",
    "aiuser optin",
    "aiuser model set",
    "aiuser prompt",
    "aiuser media images show",
    "aiuser tools status",
    "aiuser memory status",
    "aiuserowner endpoint set",
)
_REFERENCE_COMMANDS = {
    "replies": ("aiuser reply chance set", "aiuser reply mentions enable"),
    "setup": ("aiuser setup",),
}


async def can_use_config_help(ctx: commands.Context) -> bool:
    """Use the actual sender of the request, never an author in chat history."""
    if ctx.guild is None:
        return False
    if ctx.interaction:
        author = ctx.interaction.user
    else:
        message = ctx.message
        author = message.author
        if message.webhook_id is not None:
            return False
        reference = message.reference.resolved if message.reference else None
        addressed_bot = ctx.bot.user in message.mentions or (
            isinstance(reference, discord.Message) and reference.author == ctx.bot.user
        )
        if not addressed_bot:
            return False
    return not author.bot and await ctx.bot.is_owner(author)


class ConfigHelpToolCall(ToolCall):
    function_name = "inspect_aiuser_settings"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description=(
                "Use only when the bot owner's current message asks about AIUser's "
                "behavior, setup, or configuration. Read the installed cog reference "
                "and current server settings. Explain what is active and suggest a "
                "command if useful. Ask before assuming a scope. This cannot change settings."
            ),
            parameters=Parameters(
                properties={
                    "topic": {
                        "type": "string",
                        "enum": ["replies", "setup"],
                        "description": "Use replies for channels, frequency, and triggers.",
                    },
                    "channel": {
                        "type": "string",
                        "description": (
                            "Channel mention, ID, or exact name from the current question. "
                            "Omit to use the current channel."
                        ),
                    },
                },
                required=["topic"],
            ),
        )
    )

    async def _handle(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str:
        ctx = tool_context.ctx
        if not await can_use_config_help(ctx):
            return "AIUser settings are only available to the bot owner."

        topic = arguments.get("topic")
        if topic not in ("replies", "setup"):
            return "Choose replies or setup."

        services = tool_context.services
        guild_config = services.config.guild(ctx.guild)
        opt_in_by_default = await guild_config.optin_by_default()
        result: dict[str, Any] = {
            "installed_cog_source": self._source_reference(ctx, topic),
            "commands": await self._command_reference(
                ctx, _REPLY_COMMANDS if topic == "replies" else _SETUP_COMMANDS
            ),
            "server_requires_member_opt_in": not opt_in_by_default,
            "owner_has_consent": services.consent.allows(
                ctx.author.id, optin_by_default=opt_in_by_default
            ),
        }

        if topic == "setup":
            model = await guild_config.model()
            result.update(
                model=model or await services.config.default_model(),
                model_scope="server" if model else "bot default",
                tools_enabled=await guild_config.function_calling(),
                image_inputs_enabled=await guild_config.scan_images(),
                saved_memory_enabled=await guild_config.query_memories(),
                autonomous_messages_enabled=await guild_config.random_messages_enabled(),
            )
            return json.dumps(result)

        channel = self._find_channel(ctx, arguments.get("channel"))
        if channel is None:
            return "I couldn't identify a public channel with that name or ID in this server."

        parent_id = (
            channel.parent_id if isinstance(channel, discord.Thread) else channel.id
        )
        result.update(
            channel=channel.mention,
            probability_units="Fractions from 0 to 1. Commands take percentages from 0 to 100.",
            reply_channel_enabled=parent_id in await guild_config.channels_whitelist(),
            autonomous_messages_enabled=await guild_config.random_messages_enabled(),
            precedence="Member and role overrides can take precedence over channel settings.",
            reply_logic=(
                "Mentions and configured trigger words can force a reply. "
                "Recent replies can use a separate follow-up probability. "
                "Otherwise eligible message bursts use the random reply probability."
            ),
        )
        channel_config = services.config.channel(channel)
        result["reply_settings"] = {}
        for name in _REPLY_SETTINGS:
            channel_value = await getattr(channel_config, name)()
            server_value = await getattr(guild_config, name)()
            result["reply_settings"][name] = {
                "value": server_value if channel_value is None else channel_value,
                "scope": "server" if channel_value is None else "channel",
            }

        return json.dumps(result)

    @staticmethod
    def _source_reference(ctx: commands.Context, topic: str) -> dict[str, str]:
        # Fixed symbols and registered commands from the installed cog.
        functions = {"setting precedence": ScopedConfigResolver.resolve}
        for name in _REFERENCE_COMMANDS[topic]:
            command = ctx.bot.get_command(name)
            if command is not None:
                functions[name] = command.callback

        source = {}
        for name, function in functions.items():
            try:
                source[name] = inspect.getsource(function)
            except (OSError, TypeError):
                continue
        return source

    @staticmethod
    def _find_channel(ctx: commands.Context, target: Any):
        if target is None:
            return ctx.channel
        if not isinstance(target, str):
            return None

        target = target.strip().removeprefix("<#").removesuffix(">")
        if (
            target == str(ctx.channel.id)
            or target.removeprefix("#") == ctx.channel.name
        ):
            return ctx.channel
        matches = [
            channel
            for channel in ctx.guild.text_channels
            if (str(channel.id) == target or channel.name == target.removeprefix("#"))
            and channel.permissions_for(ctx.guild.default_role).view_channel
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    async def _command_reference(ctx: commands.Context, names: tuple[str, ...]):
        prefixes = await ctx.bot.get_prefix(ctx.message)
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        prefix = next(
            (prefix for prefix in prefixes if not prefix.startswith("<@")), "[p]"
        )
        reference = {}
        for name in names:
            command = ctx.bot.get_command(name)
            if command is not None:
                usage = f"{prefix}{command.qualified_name} {command.signature}".rstrip()
                reference[usage] = command.help
        return reference
