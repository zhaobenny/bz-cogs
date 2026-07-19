import logging
from typing import Optional, Union

import discord
from redbot.core import checks, commands

from aiuser.settings.scope import (
    get_effective_scoped_setting_for_target,
    get_settings_target_scope,
    parse_target_or_text,
)
from aiuser.settings.utilities import get_mention_type
from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta
from aiuser.types.types import COMPATIBLE_MENTIONS

logger = logging.getLogger("red.bz_cogs.aiuser")


class TriggerSettings(MixinMeta):
    @checks.admin_or_permissions(manage_guild=True)
    @aiuser.group(name="triggers", aliases=["trigger"])
    async def trigger(self, _):
        """Configure events that can trigger a response

        (All subcommands per server)
        """
        pass

    @trigger.group(name="public_forget", invoke_without_command=True)
    async def public_forget(self, ctx: commands.Context):
        """Show whether anyone can clear the current conversation"""
        enabled = await self.config.guild(ctx.guild).public_forget()
        return await ctx.maybe_send_embed(f"Public forget enabled: `{enabled}`")

    @public_forget.command(name="enable")
    async def public_forget_enable(self, ctx: commands.Context):
        """Allow anyone to clear the current conversation"""
        await self.config.guild(ctx.guild).public_forget.set(True)
        return await ctx.send("Public forget enabled.")

    @public_forget.command(name="disable")
    async def public_forget_disable(self, ctx: commands.Context):
        """Restrict conversation clearing to moderators"""
        await self.config.guild(ctx.guild).public_forget.set(False)
        return await ctx.send("Public forget disabled.")

    @trigger.group(name="grok", invoke_without_command=True)
    @checks.is_owner()
    async def grok(self, ctx: commands.Context):
        """Show whether the grok phrase trigger is enabled"""
        enabled = await self.config.guild(ctx.guild).grok_trigger()
        return await ctx.maybe_send_embed(f"Grok trigger enabled: `{enabled}`")

    @grok.command(name="enable")
    async def grok_enable(self, ctx: commands.Context):
        """Enable the grok phrase trigger"""
        await self.config.guild(ctx.guild).grok_trigger.set(True)
        return await ctx.send("Grok trigger enabled.")

    @grok.command(name="disable")
    async def grok_disable(self, ctx: commands.Context):
        """Disable the grok phrase trigger"""
        await self.config.guild(ctx.guild).grok_trigger.set(False)
        return await ctx.send("Grok trigger disabled.")

    @trigger.group(name="webhook")
    async def trigger_webhook(self, _):
        """Configure webhook and application bot reply settings"""
        pass

    @trigger_webhook.command(name="show")
    async def trigger_webhook_show(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Show whether webhook and application messages can trigger replies"""
        mention_type, _ = get_settings_target_scope(self, ctx, mention)
        enabled = await get_effective_scoped_setting_for_target(
            self, ctx, mention, "reply_to_webhooks"
        )
        return await ctx.maybe_send_embed(
            f"Webhook replies on this {mention_type.name.lower()}: `{enabled}`"
        )

    @trigger_webhook.command(name="enable")
    async def trigger_webhook_enable(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Allow webhook and application messages to trigger replies"""
        return await self._set_webhook_replies(ctx, mention, True)

    @trigger_webhook.command(name="disable")
    async def trigger_webhook_disable(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Prevent webhook and application messages from triggering replies"""
        return await self._set_webhook_replies(ctx, mention, False)

    @trigger_webhook.command(name="clear")
    async def trigger_webhook_clear(
        self, ctx: commands.Context, mention: COMPATIBLE_MENTIONS
    ):
        """Clear a target's webhook setting so it inherits broader settings"""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_webhooks.set(None)
        return await ctx.send(
            f"The {mention_type.name.lower()} will now inherit its webhook setting."
        )

    async def _set_webhook_replies(self, ctx, mention, enabled: bool):
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.reply_to_webhooks.set(enabled)
        return await ctx.send(
            f"Webhook replies on this {mention_type.name.lower()}: `{enabled}`"
        )

    @trigger_webhook.group(
        name="allowlist", aliases=["whitelist"], invoke_without_command=True
    )
    async def trigger_webhook_whitelist(self, ctx: commands.Context):
        """Show the webhook/app allowlist"""
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="Webhook/app user ID allowlist",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_webhook_whitelist.command(name="status")
    async def trigger_webhook_whitelist_status(self, ctx: commands.Context):
        """Show whether the webhook allowlist is enforced"""
        enabled = await self.config.guild(ctx.guild).webhook_whitelist_enabled()
        return await ctx.maybe_send_embed(f"Webhook allowlist enforced: `{enabled}`")

    @trigger_webhook_whitelist.command(name="enable")
    async def trigger_webhook_whitelist_enable(self, ctx: commands.Context):
        """Only reply to webhook users in the allowlist"""
        await self.config.guild(ctx.guild).webhook_whitelist_enabled.set(True)
        return await ctx.send("Webhook allowlist enabled.")

    @trigger_webhook_whitelist.command(name="disable")
    async def trigger_webhook_whitelist_disable(self, ctx: commands.Context):
        """Allow webhook users regardless of the allowlist"""
        await self.config.guild(ctx.guild).webhook_whitelist_enabled.set(False)
        return await ctx.send("Webhook allowlist disabled.")

    @trigger_webhook_whitelist.command(name="add")
    async def trigger_webhook_whitelist_add(self, ctx: commands.Context, user_id: int):
        """Add a user ID to the webhook/app allowlist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id in whitelist:
            return await ctx.send("That user ID is already in the allowlist")
        whitelist.append(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="The webhook/app allowlist is now:", color=await ctx.embed_color()
            ),
        )

    @trigger_webhook_whitelist.command(name="remove")
    async def trigger_webhook_whitelist_remove(
        self, ctx: commands.Context, user_id: int
    ):
        """Remove a user ID from the webhook/app allowlist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if user_id not in whitelist:
            return await ctx.send("That user ID is not in the allowlist")
        whitelist.remove(user_id)
        await self.config.guild(ctx.guild).webhook_user_whitelist.set(whitelist)
        return await self.show_webhook_whitelist(
            ctx,
            discord.Embed(
                title="The webhook/app allowlist is now:", color=await ctx.embed_color()
            ),
        )

    @trigger_webhook_whitelist.command(name="clear")
    async def trigger_webhook_whitelist_clear(self, ctx: commands.Context):
        """Clear the webhook/app allowlist"""
        await self.config.guild(ctx.guild).webhook_user_whitelist.set([])
        return await ctx.send("The webhook/app allowlist has been cleared.")

    async def show_webhook_whitelist(self, ctx: commands.Context, embed: discord.Embed):
        """Display the webhook/app allowlist"""
        whitelist = await self.config.guild(ctx.guild).webhook_user_whitelist()
        if whitelist:
            embed.description = "\n".join([f"`{user_id}`" for user_id in whitelist])
        else:
            embed.description = "No user IDs in the allowlist."
        return await ctx.send(embed=embed)

    @trigger.group(name="words", invoke_without_command=True)
    @commands.is_owner()
    async def trigger_words(
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

    @trigger_words.command(name="clear")
    async def trigger_words_clear(
        self, ctx: commands.Context, mention: Optional[COMPATIBLE_MENTIONS] = None
    ):
        """Clear a target's trigger-word override so it inherits broader settings."""
        mention_type, config_attr = get_settings_target_scope(self, ctx, mention)
        await config_attr.always_reply_on_words.set(None)
        return await ctx.send(
            f"The trigger words on this {mention_type.name.lower()} will now inherit broader settings."
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

    @trigger.group(
        name="allowlist",
        aliases=["whitelist", "whitelists"],
        invoke_without_command=True,
    )
    async def trigger_whitelist(self, ctx: commands.Context):
        """Show the trigger allowlist"""
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(
                title="Users and roles allowed to trigger replies",
                color=await ctx.embed_color(),
            ),
        )

    @trigger_whitelist.command(name="add")
    async def trigger_whitelist_add(
        self, ctx: commands.Context, new: Union[discord.Role, discord.Member]
    ):
        """Add a role or user to the allowlist"""
        if isinstance(new, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if new.id in whitelist:
                return await ctx.send("That role is already in the allowlist")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(new, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if new.id in whitelist:
                return await ctx.send("That user is already in the allowlist")
            whitelist.append(new.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)

        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The allowlist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="remove")
    async def trigger_whitelist_remove(
        self, ctx: commands.Context, rm: Union[discord.Role, discord.Member]
    ):
        """Remove a role or user from the allowlist"""
        if isinstance(rm, discord.Role):
            whitelist = await self.config.guild(ctx.guild).roles_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That role is not in the allowlist")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).roles_whitelist.set(whitelist)

        elif isinstance(rm, discord.Member):
            whitelist = await self.config.guild(ctx.guild).members_whitelist()
            if rm.id not in whitelist:
                return await ctx.send("That user is not in the allowlist")
            whitelist.remove(rm.id)
            await self.config.guild(ctx.guild).members_whitelist.set(whitelist)
        return await self.show_trigger_whitelist(
            ctx,
            discord.Embed(title="The allowlist is now:", color=await ctx.embed_color()),
        )

    @trigger_whitelist.command(name="clear")
    async def trigger_whitelist_clear(self, ctx: commands.Context):
        """Clear the allowlist so anyone can trigger replies in enabled channels"""
        await self.config.guild(ctx.guild).roles_whitelist.set([])
        await self.config.guild(ctx.guild).members_whitelist.set([])
        return await ctx.send("The allowlist has been cleared.")

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
                "Allowlist is empty\nAnyone can trigger the bot in enabled channels"
            )
        return await ctx.send(embed=embed)
