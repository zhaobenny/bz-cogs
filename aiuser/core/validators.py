# validators.py
import logging
import random
from datetime import datetime, timedelta, timezone

import discord
from redbot.core import commands

from aiuser.core.openai_utils import setup_openai_client
from aiuser.types.abc import MixinMeta
from aiuser.utils.constants import SINGULAR_MENTION_PATTERN

logger = logging.getLogger("red.bz_cogs.aiuser")


async def is_common_valid_reply(cog: MixinMeta, ctx: commands.Context) -> bool:
    """Run some common checks to see if a message is valid for the bot to reply to"""
    if not ctx.guild:
        return False
    if await cog.bot.cog_disabled_in_guild(cog, ctx.guild):
        return False
    if ctx.author.bot or not cog.channels_whitelist.get(ctx.guild.id, []):
        return False

    # Thread validation
    if not ctx.interaction:
        if (isinstance(ctx.channel, discord.Thread) and
                ctx.channel.parent.id not in cog.channels_whitelist[ctx.guild.id]):
            return False
        if (not isinstance(ctx.channel, discord.Thread) and
                ctx.channel.id not in cog.channels_whitelist[ctx.guild.id]):
            return False

    try:
        if not await cog.bot.ignored_channel_or_guild(ctx):
            return False
    except Exception:
        logger.debug("Exception in checking if ignored channel or guild", exc_info=True)
        return False

    # User permission checks
    if not await cog.bot.allowed_by_whitelist_blacklist(ctx.author):
        return False
    if ctx.author.id in await cog.config.optout():
        return False
    if (not cog.optindefault.get(ctx.guild.id) and
            (ctx.author.id not in await cog.config.optin())):
        return False

    # Content checks
    if (cog.ignore_regex.get(ctx.guild.id) and
            cog.ignore_regex[ctx.guild.id].search(ctx.message.content)):
        return False

    # Role/member whitelist checks
    whitelisted_roles = await cog.config.guild(ctx.guild).roles_whitelist()
    whitelisted_members = await cog.config.guild(ctx.guild).members_whitelist()
    if whitelisted_members or whitelisted_roles:
        if not ((ctx.author.id in whitelisted_members) or
                (ctx.author.roles and (set([role.id for role in ctx.author.roles]) &
                 set(whitelisted_roles)))):
            return False

    if not ctx.interaction and not await is_good_text_message(cog, ctx.message):
        return False

    if not cog.openai_client:
        cog.openai_client = await setup_openai_client(cog.bot, cog.config)
    if not cog.openai_client:
        return False

    return True


async def is_good_text_message(cog: MixinMeta, message: discord.Message) -> bool:
    """Validate message content"""
    if (SINGULAR_MENTION_PATTERN.match(message.content) and
            not (await is_bot_mentioned_or_replied(cog, message))):
        logger.debug(f"Skipping singular mention message {message.id} in {message.guild.name}")
        return False

    min_length = await cog.config.guild(message.guild).messages_min_length()
    if 1 <= len(message.content) < min_length:
        logger.debug(f"Skipping too short message {message.id} in {message.guild.name}")
        return False

    return True


async def is_bot_mentioned_or_replied(cog: MixinMeta, message: discord.Message) -> bool:
    """Check if message mentions or replies to bot"""
    if not await cog.config.guild(message.guild).reply_to_mentions_replies():
        return False
    return cog.bot.user in message.mentions
