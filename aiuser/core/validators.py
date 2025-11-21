import logging
from typing import Tuple

import discord
from redbot.core import commands

from aiuser.core.openai_utils import setup_openai_client
from aiuser.types.abc import MixinMeta
from aiuser.config.constants import SINGULAR_MENTION_PATTERN

logger = logging.getLogger("red.bz_cogs.aiuser")

async def is_valid_message(cog: MixinMeta, ctx: commands.Context) -> bool:
    """
    Main validation chain that runs all checks in sequence.
    Returns (is_valid, reason) tuple.
    """
    validation_chain = [
        (check_openai_client, "OpenAI Client"),
        (check_guild_permissions, "Guild Permissions"),
        (check_channel_settings, "Channel Settings"),
        (check_user_status, "User Status"),
        (check_message_content, "Message Content"),
    ]

    for validator, validation_type in validation_chain:
        try:
            is_valid, reason = await validator(cog, ctx) 
            if not is_valid:
                if validation_type in ["OpenAI Client"]:
                    logger.warning(f"Critical validation failed in '{ctx.guild.id}': {validation_type} - {reason}")
                return False
        except Exception:
            logger.error(f"Error in {validation_type} validation", exc_info=True)
            return False

    return True


async def check_openai_client(cog: MixinMeta, _ : commands.Context) -> Tuple[bool, str]:
    """Validate and setup OpenAI client"""
    if not cog.openai_client:
        cog.openai_client = await setup_openai_client(cog.bot, cog.config)
        if not cog.openai_client:
            return False, "Failed to setup OpenAI client"
    return True, ""


async def check_guild_permissions(cog: MixinMeta, ctx: commands.Context) -> Tuple[bool, str]:
    """Validate guild-level permissions and settings"""
    if not ctx.guild:
        return False, "Not in a guild"

    if await cog.bot.cog_disabled_in_guild(cog, ctx.guild):
        return False, "Cog disabled in guild"

    try:
        if not await cog.bot.ignored_channel_or_guild(ctx):
            return False, "Channel or guild ignored"
    except Exception:
        logger.debug("Exception in checking if ignored channel or guild", exc_info=True)
        return False, "Error checking channel/guild ignore status"

    return True, ""


async def check_channel_settings(cog: MixinMeta, ctx: commands.Context) -> Tuple[bool, str]:
    """Validate channel whitelist and thread settings"""
    whitelist = cog.channels_whitelist.get(ctx.guild.id, [])
    if not whitelist:
        return False, "No whitelisted channels"

    if not ctx.interaction:
        if (isinstance(ctx.channel, discord.Thread) and
                ctx.channel.parent.id not in whitelist):
            return False, "Parent channel not whitelisted"

        if (not isinstance(ctx.channel, discord.Thread) and
                ctx.channel.id not in whitelist):
            return False, "Channel not whitelisted"

    return True, ""


async def check_user_status(cog: MixinMeta, ctx: commands.Context) -> Tuple[bool, str]:
    """Validate user permissions and opt-in status"""
    # Check if message is from webhook or application bot
    is_webhook = ctx.message.webhook_id is not None
    is_app_bot = ctx.author.bot and ctx.author.id != cog.bot.user.id
    
    if is_webhook or is_app_bot:
        # Check if webhook/app replies are enabled
        reply_to_webhooks = await cog.config.guild(ctx.guild).reply_to_webhooks()
        if not reply_to_webhooks:
            return False, "Webhook/app replies disabled"
        
        # Check whitelist if enabled
        whitelist_enabled = await cog.config.guild(ctx.guild).webhook_whitelist_enabled()
        if whitelist_enabled:
            webhook_whitelist = await cog.config.guild(ctx.guild).webhook_user_whitelist()
            # Use webhook_id for webhooks, author.id for app bots
            user_id = ctx.message.webhook_id if is_webhook else ctx.author.id
            if user_id not in webhook_whitelist:
                return False, "Webhook/app not in whitelist"
        return True, ""
    
    if ctx.author.bot:
        return False, "Author is bot"

    if not await cog.bot.allowed_by_whitelist_blacklist(ctx.author):
        return False, "User not allowed by whitelist/blacklist"

    if ctx.author.id in await cog.config.optout():
        return False, "User opted out"

    if not cog.optindefault.get(ctx.guild.id) and ctx.author.id not in await cog.config.optin():
        return False, "User not opted in"

    # Role/member whitelist checks
    whitelisted_roles = await cog.config.guild(ctx.guild).roles_whitelist()
    whitelisted_members = await cog.config.guild(ctx.guild).members_whitelist()
    if whitelisted_members or whitelisted_roles:
        user_roles = set(role.id for role in ctx.author.roles) if ctx.author.roles else set()
        if not (
            (ctx.author.id in whitelisted_members) or
            (user_roles & set(whitelisted_roles))
        ):
            return False, "User not in role/member whitelist"

    return True, ""


async def check_message_content(cog: MixinMeta, ctx: commands.Context) -> Tuple[bool, str]:
    """Validate message content and format"""
    if not ctx.interaction:
        if SINGULAR_MENTION_PATTERN.match(ctx.message.content):
            if not await is_bot_mentioned_or_replied(cog, ctx.message):
                return False, "Single mention without bot reference"

        min_length = await cog.config.guild(ctx.guild).messages_min_length()
        if 1 <= len(ctx.message.content) < min_length:
            return False, f"Message too short (min: {min_length})"

    if (cog.ignore_regex.get(ctx.guild.id) and
            cog.ignore_regex[ctx.guild.id].search(ctx.message.content)):
        return False, "Message matches ignore regex"

    return True, ""

async def is_bot_mentioned_or_replied(cog: MixinMeta, message: discord.Message) -> bool:
    """Check if message mentions or replies to bot"""
    if not await cog.config.guild(message.guild).reply_to_mentions_replies():
        return False
    return cog.bot.user in message.mentions
