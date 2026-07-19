import re
from typing import Optional

import discord
from redbot.core import checks, commands

from aiuser.settings._groups import aiuser
from aiuser.settings.scope import (
    get_effective_scoped_setting_for_target,
    get_settings_target_scope,
)
from aiuser.types.abc import MixinMeta
from aiuser.types.types import COMPATIBLE_MENTIONS


class ReplySettings(MixinMeta):
    @aiuser.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def reply(self, _):
        """Configure when the bot replies"""
        pass

    @reply.group(name="chance", invoke_without_command=True)
    @checks.is_owner()
    async def reply_chance(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
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

    @reply_chance.command(name="set")
    async def reply_chance_set(
        self,
        ctx: commands.Context,
        percent: float,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Set the reply chance for the server or a target"""
        if percent < 0 or percent > 100:
            return await ctx.send("Please enter a number between 0 and 100.")

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
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its reply chance."
        )

    @reply.group(
        name="minimum_length", aliases=["minlength"], invoke_without_command=True
    )
    async def minimum_length(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
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
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Set the minimum message length for the server or a target"""
        if length < 0:
            return await ctx.send("Please enter a non-negative number.")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.messages_min_length.set(length)
        return await ctx.send(
            f"Minimum message length on this {mention_type.name.lower()} is now `{length}`."
        )

    @minimum_length.command(name="clear")
    async def minimum_length_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's minimum length so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.messages_min_length.set(None)
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its minimum message length."
        )

    @reply.group(name="ignore", invoke_without_command=True)
    async def ignore(self, ctx: commands.Context):
        """Show the regex used to ignore messages"""
        pattern = await self.config.guild(ctx.guild).ignore_regex()
        return await ctx.maybe_send_embed(f"Ignore regex: `{pattern or 'None'}`")

    @ignore.command(name="set")
    async def ignore_set(self, ctx: commands.Context, *, regex_pattern: str):
        """Set the regex used to ignore messages"""
        try:
            await self.services.ignore_regex_cache.set_ignore_regex(
                ctx.guild, regex_pattern
            )
        except re.error:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        return await ctx.send(f"The ignore regex is now `{regex_pattern}`.")

    @ignore.command(name="clear")
    async def ignore_clear(self, ctx: commands.Context):
        """Clear the regex used to ignore messages"""
        await self.services.ignore_regex_cache.set_ignore_regex(ctx.guild, None)
        return await ctx.send("The ignore regex has been cleared.")

    @reply.group(name="followup")
    @checks.is_owner()
    async def followup(self, _):
        """Configure replies that continue a recent conversation"""
        pass

    @followup.group(name="chance", invoke_without_command=True)
    async def followup_chance(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
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
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Set the conversation follow-up chance"""
        if percent < 0 or percent > 100:
            return await ctx.send("Please enter a number between 0 and 100.")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_percent.set(percent / 100)
        return await ctx.send(
            f"Follow-up chance on this {mention_type.name.lower()} is now `{percent:.2f}%`."
        )

    @followup_chance.command(name="clear")
    async def followup_chance_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's follow-up chance so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_percent.set(None)
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its follow-up chance."
        )

    @followup.group(name="window", invoke_without_command=True)
    async def followup_window(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
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
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Set the conversation follow-up window"""
        if seconds < 0:
            return await ctx.send("Please enter a non-negative number.")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_time.set(seconds)
        return await ctx.send(
            f"Follow-up window on this {mention_type.name.lower()} is now `{seconds}` seconds."
        )

    @followup_window.command(name="clear")
    async def followup_window_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's follow-up window so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.conversation_reply_time.set(None)
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its follow-up window."
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
            return await ctx.send("Please enter a positive number.")

        await self.config.guild(ctx.guild).message_burst_idle_seconds.set(seconds)
        return await ctx.send(f"Message burst idle window is now `{seconds}` seconds.")

    @message_burst.command(name="max")
    async def message_burst_max(self, ctx: commands.Context, seconds: int):
        """Set maximum seconds a message burst can stay open"""
        if seconds <= 0:
            return await ctx.send("Please enter a positive number.")

        await self.config.guild(ctx.guild).message_burst_max_seconds.set(seconds)
        return await ctx.send(
            f"Message burst maximum window is now `{seconds}` seconds."
        )

    @reply.group(name="mentions", invoke_without_command=True)
    @checks.is_owner()
    async def mentions(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
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
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Always reply to mentions and replies for the server or a target"""
        return await self._set_mentions(ctx, mention, True)

    @mentions.command(name="disable")
    async def mentions_disable(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        """Do not force replies to mentions for the server or a target"""
        return await self._set_mentions(ctx, mention, False)

    @mentions.command(name="clear")
    async def mentions_clear(self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS):
        """Clear a target's mention setting so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_mentions_replies.set(None)
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its mention reply setting."
        )

    async def _set_mentions(self, ctx, mention, enabled: bool):
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_mentions_replies.set(enabled)
        return await ctx.send(
            f"Always reply to mentions on this {mention_type.name.lower()}: `{enabled}`"
        )
