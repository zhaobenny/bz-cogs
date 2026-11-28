from __future__ import annotations

import re
from typing import Optional

import discord
from redbot.core import checks, commands

from aiuser.providers.decision import (
    resolve_decision_provider,
    resolve_decision_provider_name,
)
from aiuser.settings._groups import aiuser
from aiuser.settings.scope import (
    get_effective_scoped_setting_for_target,
    get_settings_target_scope,
)
from aiuser.types.abc import MixinMeta
from aiuser.types.enums import ReplyMode
from aiuser.types.types import (
    COMPATIBLE_CHANNEL_TYPES,
    COMPATIBLE_CHANNELS,
    COMPATIBLE_MENTIONS,
)
from aiuser.utils.utilities import truncate_text


class ReplySettings(MixinMeta):
    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def reply(self, _):
        """Configure when the bot replies"""

    @reply.group(name="chance", invoke_without_command=True)
    @checks.is_owner()
    async def reply_chance(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show the effective reply chance for the server or a target"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        percent = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "reply_percent"
        )
        return await ctx.maybe_send_embed(
            f"Effective reply chance on this {mention_type.name.lower()}: "
            f"`{percent * 100:.2f}%`"
        )

    async def _refuse_if_decision_mode(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS | None
    ) -> bool:
        channel_for_mode = (
            mention if isinstance(mention, COMPATIBLE_CHANNEL_TYPES) else None
        )
        effective_mode = await self.services.resolver.resolve_reply_mode(
            guild=ctx.guild, channel=channel_for_mode
        )
        if effective_mode is ReplyMode.DECISION:
            target_label = "this channel" if channel_for_mode else "this server"
            await ctx.maybe_send_embed(
                f"Reply mode on {target_label} is currently `{ReplyMode.DECISION.value}`. "
                f"Switch with `{ctx.clean_prefix}aiuser reply mode {ReplyMode.CHANCE.value}` first."
            )
            return True
        return False

    @reply_chance.command(name="set")
    async def reply_chance_set(
        self,
        ctx: commands.Context,
        percent: float,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Set the reply chance for the server or a target"""
        if percent < 0 or percent > 100:
            return await ctx.maybe_send_embed(
                "Please enter a number between 0 and 100."
            )

        if await self._refuse_if_decision_mode(ctx, mention):
            return

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_percent.set(percent / 100)
        embed = discord.Embed(
            title=f"Reply chance on this {mention_type.name.lower()} is now:",
            description=f"{percent:.2f}%",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @reply_chance.command(name="clear")
    async def reply_chance_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's reply chance so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_percent.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit its reply chance."
        )

    @reply.group(
        name="minimum_length", aliases=["minlength"], invoke_without_command=True
    )
    async def minimum_length(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show the effective minimum message length for a target"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        length = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "messages_min_length"
        )
        return await ctx.maybe_send_embed(
            f"Minimum message length on this {mention_type.name.lower()}: `{length}`"
        )

    @minimum_length.command(name="set")
    async def minimum_length_set(
        self,
        ctx: commands.Context,
        length: int,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Set the minimum message length for the server or a target"""
        if length < 0:
            return await ctx.maybe_send_embed("Please enter a non-negative number.")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.messages_min_length.set(length)
        return await ctx.maybe_send_embed(
            f"Minimum message length on this {mention_type.name.lower()} is now `{length}`."
        )

    @minimum_length.command(name="clear")
    async def minimum_length_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's minimum length so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.messages_min_length.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit its minimum message length."
        )

    @reply.group(name="ignore", invoke_without_command=True)
    async def ignore(self, ctx: commands.Context):
        """Show the regex used to ignore messages"""
        pattern = await self.config.guild(ctx.guild).ignore_regex()
        display_pattern = truncate_text(pattern) if pattern else "None"
        return await ctx.maybe_send_embed(f"Ignore regex: `{display_pattern}`")

    @ignore.command(name="set")
    async def ignore_set(self, ctx: commands.Context, *, regex_pattern: str):
        """Set the regex used to ignore messages"""
        try:
            await self.services.ignore_regex_cache.set_ignore_regex(
                ctx.guild, regex_pattern
            )
        except re.error:
            return await ctx.maybe_send_embed(
                "Sorry, but that regex pattern seems to be invalid."
            )
        return await ctx.maybe_send_embed(
            f"The ignore regex is now `{truncate_text(regex_pattern)}`."
        )

    @ignore.command(name="clear")
    async def ignore_clear(self, ctx: commands.Context):
        """Clear the regex used to ignore messages"""
        await self.services.ignore_regex_cache.set_ignore_regex(ctx.guild, None)
        return await ctx.maybe_send_embed("The ignore regex has been cleared.")

    @reply.group(name="followup")
    @checks.is_owner()
    async def followup(self, _):
        """Configure replies that continue a recent conversation"""

    @followup.group(name="chance", invoke_without_command=True)
    async def followup_chance(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show the effective conversation follow-up chance"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        percent = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "conversation_reply_percent"
        )
        return await ctx.maybe_send_embed(
            f"Follow-up chance on this {mention_type.name.lower()}: `{percent * 100:.2f}%`"
        )

    @followup_chance.command(name="set")
    async def followup_chance_set(
        self,
        ctx: commands.Context,
        percent: float,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Set the conversation follow-up chance"""
        if percent < 0 or percent > 100:
            return await ctx.maybe_send_embed(
                "Please enter a number between 0 and 100."
            )

        if await self._refuse_if_decision_mode(ctx, mention):
            return

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_percent.set(percent / 100)
        return await ctx.maybe_send_embed(
            f"Follow-up chance on this {mention_type.name.lower()} is now `{percent:.2f}%`."
        )

    @followup_chance.command(name="clear")
    async def followup_chance_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's follow-up chance so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_percent.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit its follow-up chance."
        )

    @followup.group(name="window", invoke_without_command=True)
    async def followup_window(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show the effective conversation follow-up window"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        seconds = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "conversation_reply_time"
        )
        return await ctx.maybe_send_embed(
            f"Follow-up window on this {mention_type.name.lower()}: `{seconds}` seconds"
        )

    @followup_window.command(name="set")
    async def followup_window_set(
        self,
        ctx: commands.Context,
        seconds: int,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Set the conversation follow-up window"""
        if seconds < 0:
            return await ctx.maybe_send_embed("Please enter a non-negative number.")

        if await self._refuse_if_decision_mode(ctx, mention):
            return

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_time.set(seconds)
        return await ctx.maybe_send_embed(
            f"Follow-up window on this {mention_type.name.lower()} is now `{seconds}` seconds."
        )

    @followup_window.command(name="clear")
    async def followup_window_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's follow-up window so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_time.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit its follow-up window."
        )

    @reply.group(name="mode", invoke_without_command=True)
    @checks.is_owner()
    async def reply_mode(
        self,
        ctx: commands.Context,
        channel: Optional[COMPATIBLE_CHANNELS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show whether replies use percentage chance or a decision model"""
        mention_type, _ = get_settings_target_scope(self, ctx, channel)
        mode = await self.services.resolver.resolve_reply_mode(
            guild=ctx.guild, channel=channel
        )
        embed = discord.Embed(
            title=f"Reply mode on this {mention_type.name.lower()}",
            description=f"`{mode.value}`",
            color=await ctx.embed_color(),
        )
        if mode is ReplyMode.DECISION:
            resolved = await resolve_decision_provider(self.services)
            if resolved is not None:
                provider, model = resolved
                embed.add_field(
                    name="Decision Backend",
                    value=f"`{provider.name}` (`{model}`)",
                    inline=False,
                )
            else:
                provider_name = await resolve_decision_provider_name(self.services)
                if provider_name:
                    missing_msg = (
                        f"Set the `{provider_name}` API key with "
                        f"`{ctx.clean_prefix}set api {provider_name} api_key,VALUE`."
                    )
                else:
                    missing_msg = (
                        "Current chat endpoint has no Decisions API. Configure one explicitly with "
                        f"`{ctx.clean_prefix}aiuserowner decision provider set <openrouter|openai|typesafe>`."
                    )
                embed.add_field(
                    name="Decision Backend Unavailable",
                    value=missing_msg,
                    inline=False,
                )
        return await ctx.send(embed=embed)

    @reply_mode.command(name="chance")
    async def reply_mode_chance(
        self,
        ctx: commands.Context,
        channel: Optional[COMPATIBLE_CHANNELS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Use percentage-based reply chance for the server or a channel"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, channel)
        await config_attr.reply_mode.set(ReplyMode.CHANCE.value)
        return await ctx.maybe_send_embed(
            f"Reply mode on this {mention_type.name.lower()} is now `{ReplyMode.CHANCE.value}`."
        )

    @reply_mode.command(name="decision")
    async def reply_mode_decision(
        self,
        ctx: commands.Context,
        channel: Optional[COMPATIBLE_CHANNELS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Use a decision model to decide when to reply for the server or a channel"""
        resolved = await resolve_decision_provider(self.services)
        if resolved is None:
            provider_name = await resolve_decision_provider_name(self.services)
            if provider_name:
                return await ctx.maybe_send_embed(
                    f"Decision mode needs the `{provider_name}` API key. "
                    f"Set it with `{ctx.clean_prefix}set api {provider_name} api_key,VALUE`."
                )
            return await ctx.maybe_send_embed(
                "The current chat endpoint does not have a built-in Decisions API. "
                "Set an explicit decision provider with "
                f"`{ctx.clean_prefix}aiuserowner decision provider set <openrouter|openai|typesafe>` first."
            )

        provider, model = resolved
        mention_type, config_attr = get_settings_target_scope(self, ctx, channel)
        await config_attr.reply_mode.set(ReplyMode.DECISION.value)
        embed = discord.Embed(
            title=f"Reply mode on this {mention_type.name.lower()} is now `{ReplyMode.DECISION.value}`",
            description=f"Using `{provider.name}` (`{model}`).",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @reply_mode.command(name="clear")
    async def reply_mode_clear(
        self,
        ctx: commands.Context,
        channel: COMPATIBLE_CHANNELS,
    ):
        """Clear a channel's reply mode so it inherits the server setting"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, channel)
        await config_attr.reply_mode.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit the server reply mode."
        )

    @reply.group(name="burst", invoke_without_command=True)
    @checks.is_owner()
    async def message_burst(self, ctx: commands.Context):
        """Show message batching timing"""
        guild_config = self.config.guild(ctx.guild)
        idle = await guild_config.message_burst_idle_seconds()
        maximum = await guild_config.message_burst_max_seconds()
        return await ctx.maybe_send_embed(
            f"Burst timing: idle `{idle}`s, maximum `{maximum}`s"
        )

    @message_burst.command(name="idle")
    async def message_burst_idle(self, ctx: commands.Context, seconds: int):
        """Set seconds of quiet before a message burst can close"""
        if seconds <= 0:
            return await ctx.maybe_send_embed("Please enter a positive number.")

        await self.config.guild(ctx.guild).message_burst_idle_seconds.set(seconds)
        return await ctx.maybe_send_embed(
            f"Message burst idle window is now `{seconds}` seconds."
        )

    @message_burst.command(name="max")
    async def message_burst_max(self, ctx: commands.Context, seconds: int):
        """Set maximum seconds a message burst can stay open"""
        if seconds <= 0:
            return await ctx.maybe_send_embed("Please enter a positive number.")

        await self.config.guild(ctx.guild).message_burst_max_seconds.set(seconds)
        return await ctx.maybe_send_embed(
            f"Message burst maximum window is now `{seconds}` seconds."
        )

    @reply.group(name="mentions", invoke_without_command=True)
    @checks.is_owner()
    async def mentions(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Show whether mentions and replies always trigger a response"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        enabled = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "reply_to_mentions_replies"
        )
        return await ctx.maybe_send_embed(
            f"Always reply to mentions on this {mention_type.name.lower()}: `{enabled}`"
        )

    @mentions.command(name="enable")
    async def mentions_enable(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Always reply to mentions and replies for the server or a target"""
        return await self._set_mentions(ctx, mention, True)

    @mentions.command(name="disable")
    async def mentions_disable(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,  # noqa: UP045 - Red evaluates command converters on Python 3.9
    ):
        """Do not force replies to mentions for the server or a target"""
        return await self._set_mentions(ctx, mention, False)

    @mentions.command(name="clear")
    async def mentions_clear(self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS):
        """Clear a target's mention setting so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_mentions_replies.set(None)
        return await ctx.maybe_send_embed(
            f"The {mention_type.name.lower()} will now inherit its mention reply setting."
        )

    async def _set_mentions(self, ctx, mention, enabled: bool):
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_mentions_replies.set(enabled)
        return await ctx.maybe_send_embed(
            f"Always reply to mentions on this {mention_type.name.lower()}: `{enabled}`"
        )
