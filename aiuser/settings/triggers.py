import logging
import re
from typing import Optional, Union

import discord
from redbot.core import checks, commands

from aiuser.settings.scope import (
    get_broader_scoped_setting_for_target,
    get_effective_scoped_setting_for_target,
    get_settings_target_scope,
    parse_target_or_text,
    parse_target_or_value,
)
from aiuser.settings.utilities import get_mention_type
from aiuser.types.abc import MixinMeta, aiuser
from aiuser.types.enums import MentionType
from aiuser.types.types import COMPATIBLE_MENTIONS

logger = logging.getLogger("red.bz_cogs.aiuser")


class TriggerSettings(MixinMeta):
    @checks.admin_or_permissions(manage_guild=True)
    @aiuser.group()
    async def trigger(self, _):
        """Configure trigger settings for the bot to respond to

        (All subcommands per server)
        """
        pass

    @trigger.command(name="minlength", aliases=["min_length"])
    async def min_length(
        self,
        ctx: commands.Context,
        mention_or_length: Optional[Union[COMPATIBLE_MENTIONS, int]],
        length: Optional[int] = None,
    ):
        """Set minimum message length for server, or a specific user/role/channel"""
        mention, length = parse_target_or_value(mention_or_length, length)
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)

        if length is None and mention_type == MentionType.SERVER:
            return await ctx.send(":warning: No length provided")
        if length is not None and length < 0:
            return await ctx.send("Please enter a non-negative number")

        if length is not None or mention_type == MentionType.SERVER:
            await config_attr.messages_min_length.set(length)
            desc = str(length)
        else:
            await config_attr.messages_min_length.set(None)
            desc = "`Custom minimum length cleared, will use broader level settings`"

        embed = discord.Embed(
            title=f"Minimum message length on this {mention_type.name.lower()} is now:",
            description=desc,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="ignore", aliases=["ignoreregex"])
    async def ignore(self, ctx: commands.Context, *, regex_pattern: Optional[str]):
        """Messages matching this regex won't be replied to or seen, by the bot"""
        if not regex_pattern:
            await self.config.guild(ctx.guild).ignore_regex.set(None)
            self.ignore_regex[ctx.guild.id] = None
            return await ctx.send("The ignore regex has been cleared.")
        try:
            self.ignore_regex[ctx.guild.id] = re.compile(regex_pattern)
        except Exception:
            return await ctx.send("Sorry, but that regex pattern seems to be invalid.")
        await self.config.guild(ctx.guild).ignore_regex.set(regex_pattern)
        embed = discord.Embed(
            title="The ignore regex is now:",
            description=f"`{regex_pattern}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @checks.is_owner()
    @trigger.command(name="conversation_reply_percent")
    async def conversation_reply_percent(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS],
        percent: Optional[float],
    ):
        """Set conversation follow-up reply chance for server, or a specific user/role/channel

        If multiple percentages can be used, the most specific one is used: member > role > channel > server

        **Arguments**
            - `mention` (Optional) A mention of a user, role, or channel
            - `percent` (Optional) A number between 0 and 100, if omitted, resets custom value for non-server targets
        """
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)

        if percent is None and mention_type == MentionType.SERVER:
            return await ctx.send(":warning: No percent provided")
        if percent is not None and (percent < 0 or percent > 100):
            return await ctx.send("Please enter a number between 0 and 100")

        if percent is not None or mention_type == MentionType.SERVER:
            await config_attr.conversation_reply_percent.set(percent / 100)
            desc = f"{percent:.2f}%"
        else:
            await config_attr.conversation_reply_percent.set(None)
            desc = (
                "`Custom conversation percent cleared, will use broader level settings`"
            )

        embed = discord.Embed(
            title=f"Conversation follow-up response chance on this {mention_type.name.lower()} is now:",
            description=desc,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @checks.is_owner()
    @trigger.command(name="conversation_reply_time")
    async def conversation_reply_time(
        self,
        ctx: commands.Context,
        mention: Optional[COMPATIBLE_MENTIONS],
        seconds: Optional[int],
    ):
        """Set conversation follow-up time window in seconds for server, or a specific user/role/channel

        If multiple values can be used, the most specific one is used: member > role > channel > server

        **Arguments**
            - `mention` (Optional) A mention of a user, role, or channel
            - `seconds` (Optional) A positive number, if omitted, resets custom value for non-server targets
        """
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)

        if seconds is None and mention_type == MentionType.SERVER:
            return await ctx.send(":warning: No seconds provided")
        if seconds is not None and seconds < 0:
            return await ctx.send("Please enter a positive number")

        if seconds is not None or mention_type == MentionType.SERVER:
            await config_attr.conversation_reply_time.set(seconds)
            desc = f"{seconds} seconds"
        else:
            await config_attr.conversation_reply_time.set(None)
            desc = (
                "`Custom conversation window cleared, will use broader level settings`"
            )

        embed = discord.Embed(
            title=f"Conversation follow-up window on this {mention_type.name.lower()} is now:",
            description=desc,
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="reply_to_mentions", aliases=["mentions_replies"])
    @checks.is_owner()
    async def force_reply_to_mentions(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Toggle mention/reply triggering for server, or a specific user/role/channel"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        current = await config_attr.reply_to_mentions_replies()
        if current is None and mention_type != MentionType.SERVER:
            current = await get_broader_scoped_setting_for_target(
                self, ctx, mention, "reply_to_mentions_replies"
            )
        value = not current
        await config_attr.reply_to_mentions_replies.set(value)
        embed = discord.Embed(
            title=f"Always replying to mentions/replies on this {mention_type.name.lower()} is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command()
    async def public_forget(self, ctx: commands.Context):
        """Toggles whether anyone can use the forget command, or only moderators"""
        value = not await self.config.guild(ctx.guild).public_forget()
        await self.config.guild(ctx.guild).public_forget.set(value)
        embed = discord.Embed(
            title="Anyone can use the forget command:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.command(name="grok")
    @checks.is_owner()
    async def grok(self, ctx: commands.Context):
        """Toggles a simple trigger where it always respond on an short message (less than 25 words) containng the word 'grok' or 'gork' AND 'true' or 'explain' or 'confirm'"""
        value = not await self.config.guild(ctx.guild).grok_trigger()
        await self.config.guild(ctx.guild).grok_trigger.set(value)
        embed = discord.Embed(
            title="The grok trigger is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger.group(name="webhook")
    async def trigger_webhook(self, _):
        """Configure webhook and application bot reply settings"""
        pass

    @trigger_webhook.command(name="toggle")
    async def trigger_webhook_toggle(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Toggle webhook/app-bot replies for server, or a specific user/role/channel"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        current = await config_attr.reply_to_webhooks()
        if current is None and mention_type != MentionType.SERVER:
            current = await get_broader_scoped_setting_for_target(
                self, ctx, mention, "reply_to_webhooks"
            )
        value = not current
        await config_attr.reply_to_webhooks.set(value)
        embed = discord.Embed(
            title=f"Replying to webhooks and apps on this {mention_type.name.lower()} is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger_webhook.group(name="whitelist")
    async def trigger_webhook_whitelist(self, _):
        """Configure user ID whitelist for webhooks and application bots"""
        pass

    @trigger_webhook_whitelist.command(name="toggle")
    async def trigger_webhook_whitelist_toggle(self, ctx: commands.Context):
        """Toggles if the whitelist filtering is enabled for webhooks/apps"""
        value = not await self.config.guild(ctx.guild).webhook_whitelist_enabled()
        await self.config.guild(ctx.guild).webhook_whitelist_enabled.set(value)
        embed = discord.Embed(
            title="Webhook/app whitelist filtering is now:",
            description=f"{value}",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @trigger_webhook_whitelist.command(name="add")
    async def trigger_webhook_whitelist_add(self, ctx: commands.Context, user_id: int):
        """Add a user ID to the webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id in whitelist:
            return await ctx.send("That user ID is already in the whitelist")
        whitelist.append(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="The webhook/app whitelist is now:", color=await ctx.embed_color()
            ),
        )

    @trigger_webhook_whitelist.command(name="remove")
    async def trigger_webhook_whitelist_remove(
        self, ctx: commands.Context, user_id: int
    ):
        """Remove a user ID from the webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id not in whitelist:
            return await ctx.send("That user ID is not in the whitelist")
        whitelist.remove(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="The webhook/app whitelist is now:", color=await ctx.embed_color()
            ),
        )

    @trigger_webhook_whitelist.command(name="list", aliases=["show"])
    async def trigger_webhook_whitelist_list(self, ctx: commands.Context):
        """Show the webhook/app whitelist"""
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="Webhook/app user ID whitelist",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_webhook_whitelist.command(name="clear")
    async def trigger_webhook_whitelist_clear(self, ctx: commands.Context):
        """Clear the webhook/app whitelist"""
        await self.config.guild(ctx.guild).webhook_user_whitelist.set([])
        return await ctx.send("The webhook/app whitelist has been cleared.")

    async def show_webhook_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        """Helper function to display webhook/app whitelist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if whitelist:
            embed.description = "\n".join([f"`{user_id}`" for user_id in whitelist])
        else:
            embed.description = "No user IDs whitelisted."
        return await ctx.send(embed=embed)

    @trigger.group(name="words")
    @commands.is_owner()
    async def trigger_words(self, _):
        """Configure a list of words that will make the bot always be triggered to respond to a message"""
        pass

    @trigger_words.command(name="add")
    async def trigger_words_add(
        self,
        ctx: commands.Context,
        mention_or_word: Union[COMPATIBLE_MENTIONS, str],
        *,
        word: Optional[str] = None,
    ):
        """Add a word to the trigger words list (server or target override)."""
        mention, word = parse_target_or_text(mention_or_word, word)
        if not word:
            return await ctx.send(":warning: No word provided")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        words = list(
            await get_effective_scoped_setting_for_target(
                self, ctx, mention, "always_reply_on_words"
            )
            or []
        )
        if word in words:
            return await ctx.send("That word is already in the list")
        words.append(word)
        await config_attr.always_reply_on_words.set(words)
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title=f"The trigger words on this {mention_type.name.lower()} are now:",
                color=await ctx.embed_color(),
            ),
            mention=mention,
        )

    @trigger_words.command(name="remove")
    async def trigger_words_remove(
        self,
        ctx: commands.Context,
        mention_or_word: Union[COMPATIBLE_MENTIONS, str],
        *,
        word: Optional[str] = None,
    ):
        """Remove a word from the trigger words list (server or target override)."""
        mention, word = parse_target_or_text(mention_or_word, word)
        if not word:
            return await ctx.send(":warning: No word provided")

        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        words = list(
            await get_effective_scoped_setting_for_target(
                self, ctx, mention, "always_reply_on_words"
            )
            or []
        )
        if word not in words:
            return await ctx.send("That word is not in the list")
        words.remove(word)
        await config_attr.always_reply_on_words.set(words)
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title=f"The trigger words on this {mention_type.name.lower()} are now:",
                color=await ctx.embed_color(),
            ),
            mention=mention,
        )

    @trigger_words.command(name="list", aliases=["show"])
    async def trigger_words_list(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Show the effective trigger words list for a target."""
        mention_type = get_mention_type(mention)
        return await self.show_trigger_always_words(
            ctx,
            discord.Embed(
                title=f"Trigger words on this {mention_type.name.lower()}",
                color=await ctx.embed_color(),
            ),
            mention=mention,
        )

    @trigger_words.command(name="clear")
    async def trigger_words_clear(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Clear the trigger words list for a target (empty override)."""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.always_reply_on_words.set([])
        return await ctx.send(
            f"The trigger words list on this {mention_type.name.lower()} has been cleared."
        )

    @trigger_words.command(name="reset")
    async def trigger_words_reset(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Reset a user/role/channel trigger word override to inherit broader settings."""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.always_reply_on_words.set(None)
        return await ctx.send(
            f"The trigger words override on this {mention_type.name.lower()} has been reset."
        )

    async def show_trigger_always_words(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        mention: Optional[COMPATIBLE_MENTIONS] = None,
    ):
        words = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "always_reply_on_words"
        )
        if words:
            embed.description = ", ".join(f"`{word}`" for word in words)
        else:
            embed.description = "No trigger words set."
        return await ctx.send(embed=embed)

    @trigger.group(name="whitelist", aliases=["whitelists"])
    async def trigger_whitelist(self, ctx: commands.Context):
        """If configured, only whitelisted roles / users can trigger a response in whitelisted channels"""
        pass

    @trigger_whitelist.command(name="add")
    async def trigger_whitelist_add(
        self, ctx: commands.Context, new: Union[discord.Role, discord.Member]
    ):
        """Add a role/user to the whitelist"""
        if isinstance(new, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if new.id in whitelist:
                return await ctx.send("That role is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(new, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if new.id in whitelist:
                return await ctx.send("That user is already whitelisted")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)

        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="remove")
    async def trigger_whitelist_remove(
        self, ctx: commands.Context, rm: Union[discord.Role, discord.Member]
    ):
        """Remove a user/role from the whitelist"""
        if isinstance(rm, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That role is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(rm, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That user is not whitelisted")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The whitelist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="list", aliases=["show"])
    async def trigger_whitelist_list(self, ctx: commands.Context):
        """Show the whitelist"""
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(
                title="Whitelist of users/roles that will trigger LLM",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_whitelist.command(name="clear")
    async def trigger_whitelist_clear(self, ctx: commands.Context):
        """Clear the whitelist, allowing anyone to trigger LLM in whitelisted channels"""
        await self.config.guild(ctx.guild).roles_whitelist.set([])
        await self.config.guild(ctx.guild).members_whitelist.set([])
        return await ctx.send("The whitelist has been cleared.")

    async def show_trigger_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        roles_whitelist = await self.config.guild(ctx.guild).roles_whitelist()
        users_whitelist = await self.config.guild(ctx.guild).members_whitelist()
        if roles_whitelist:
            embed.add_field(
                name="Roles",
                value="\n".join([f"<@&{r}>" for r in roles_whitelist]),
                inline=False,
            )
        if users_whitelist:
            embed.add_field(
                name="Users",
                value="\n".join([f"<@{u}>" for u in users_whitelist]),
                inline=False,
            )
        if not roles_whitelist and not users_whitelist:
            embed.description = (
                "Nothing whitelisted\nAnyone can trigger bot in whitelisted channels"
            )
        return await ctx.send(embed=embed)
