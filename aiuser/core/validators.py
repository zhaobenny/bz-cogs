"""The validation chain deciding whether a message may get a response."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Tuple

import discord
from redbot.core import commands

from aiuser.config.constants import SINGULAR_MENTION_PATTERN
from aiuser.utils.adapters import ensure_member_like

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


async def is_valid_message(services: "AIUserServices", ctx: commands.Context) -> bool:
    """
    Main validation chain that runs all checks in sequence.
    """
    validation_chain = [
        (check_guild_permissions, "Guild Permissions"),
        (check_channel_settings, "Channel Settings"),
        (check_user_status, "User Status"),
        (check_message_content, "Message Content"),
    ]

    for validator, validation_type in validation_chain:
        try:
            is_valid, reason = await validator(services, ctx)
            if not is_valid:
                logger.debug(f"Validation failed at: {validation_type} - {reason}")
                return False
        except Exception:
            logger.error(f"Error in {validation_type} validation", exc_info=True)
            return False

    return True


async def check_guild_permissions(
    services: "AIUserServices", ctx: commands.Context
) -> Tuple[bool, str]:
    """Validate guild-level permissions and settings"""
    if not ctx.guild:
        return False, "Not in a guild"

    if await services.bot.cog_disabled_in_guild(services.cog, ctx.guild):
        return False, "Cog disabled in guild"

    # bot.ignored_channel_or_guild expects Member objects
    ctx.author = ensure_member_like(ctx.author)

    try:
        if not await services.bot.ignored_channel_or_guild(ctx):
            return False, "Channel or guild ignored"
    except Exception:
        logger.debug("Exception in checking if ignored channel or guild", exc_info=True)
        return False, "Error checking channel/guild ignore status"

    return True, ""


async def check_channel_settings(
    services: "AIUserServices", ctx: commands.Context
) -> Tuple[bool, str]:
    """Validate channel whitelist and thread settings"""
    whitelist = services.guild_cache.channels_whitelist(ctx.guild.id)
    if not whitelist:
        return False, "No whitelisted channels"

    if not ctx.interaction:
        if (
            isinstance(ctx.channel, discord.Thread)
            and ctx.channel.parent.id not in whitelist
        ):
            return False, "Parent channel not whitelisted"

        if (
            not isinstance(ctx.channel, discord.Thread)
            and ctx.channel.id not in whitelist
        ):
            return False, "Channel not whitelisted"

    return True, ""


async def check_user_status(
    services: "AIUserServices", ctx: commands.Context
) -> Tuple[bool, str]:
    """Validate user permissions and opt-in status"""
    if ctx.author.id == services.bot.user.id:
        return False, "Ignoring self-authored bot message"

    # Check if message is from webhook or application bot
    is_webhook = ctx.message.webhook_id is not None
    is_app_bot = ctx.author.bot and ctx.author.id != services.bot.user.id

    if is_webhook or is_app_bot:
        # Check if webhook/app replies are enabled
        reply_to_webhooks = await services.resolver.resolve_for_ctx(
            "reply_to_webhooks", ctx
        )
        if not reply_to_webhooks:
            return False, "Webhook/app replies disabled"

        # Check whitelist if enabled
        whitelist_enabled = await services.config.guild(
            ctx.guild
        ).webhook_whitelist_enabled()
        if whitelist_enabled:
            webhook_whitelist = await services.config.guild(
                ctx.guild
            ).webhook_user_whitelist()
            # Use webhook_id for webhooks, author.id for app bots
            user_id = ctx.message.webhook_id if is_webhook else ctx.author.id
            if user_id not in webhook_whitelist:
                return False, "Webhook/app not in whitelist"
        return True, ""

    if ctx.author.bot:
        return False, f"User {ctx.author.name} is bot"

    if not await services.bot.allowed_by_whitelist_blacklist(ctx.author):
        return False, f"User {ctx.author.name} not allowed by whitelist/blacklist"

    if services.consent.is_opted_out(ctx.author.id):
        return False, "User opted out"

    if not services.guild_cache.optin_by_default(
        ctx.guild.id
    ) and not services.consent.is_opted_in(ctx.author.id):
        return False, "User not opted in"

    # Role/member whitelist checks
    whitelisted_roles = await services.config.guild(ctx.guild).roles_whitelist()
    whitelisted_members = await services.config.guild(ctx.guild).members_whitelist()
    if whitelisted_members or whitelisted_roles:
        # Webhook messages have User objects instead of Member objects
        if isinstance(ctx.author, discord.Member):
            user_roles = (
                set(role.id for role in ctx.author.roles) if ctx.author.roles else set()
            )
        else:
            user_roles = set()
        if not (
            (ctx.author.id in whitelisted_members)
            or (user_roles & set(whitelisted_roles))
        ):
            return False, f"User {ctx.author.name} not in role/member whitelist"

    return True, ""


async def check_message_content(
    services: "AIUserServices", ctx: commands.Context
) -> Tuple[bool, str]:
    """Validate message content and format"""
    if not ctx.interaction:
        if SINGULAR_MENTION_PATTERN.match(ctx.message.content):
            if not await is_bot_mentioned_or_replied(services, ctx.message):
                return False, "Single mention without bot reference"

        min_length = await services.resolver.resolve_for_ctx("messages_min_length", ctx)
        if 1 <= len(ctx.message.content) < min_length:
            return False, f"Message too short (min: {min_length})"

    ignore_regex = services.guild_cache.ignore_regex(ctx.guild.id)
    if ignore_regex and ignore_regex.search(ctx.message.content):
        return False, "Message matches ignore regex"

    return True, ""


async def is_bot_mentioned_or_replied(
    services: "AIUserServices", message: discord.Message
) -> bool:
    """Check if message mentions or replies to bot"""
    if not await services.resolver.resolve_for_message(
        "reply_to_mentions_replies", message
    ):
        return False
    return services.bot.user in message.mentions
