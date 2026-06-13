"""Entry points for message / slash-command events."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

import discord
from redbot.core import commands

from aiuser.config.constants import URL_PATTERN
from aiuser.config.defaults import DEFAULT_REPLY_PERCENT
from aiuser.core.triggers import check_triggers
from aiuser.core.validators import is_valid_message
from aiuser.response.response import create_response
from aiuser.utils.logging_context import with_discord_log_context
from aiuser.utils.utilities import is_embed_valid

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


@with_discord_log_context("slash-command")
async def handle_slash_command(
    services: "AIUserServices", inter: discord.Interaction, text: str
):
    """Handle /chat slash command interactions"""
    await inter.response.defer()

    ctx = await commands.Context.from_interaction(inter)
    ctx.message.content = text

    if not (await is_valid_message(services, ctx)):
        return await ctx.send(
            "You're not allowed to use this command here.", ephemeral=True
        )
    elif await get_percentage(services, ctx) == 1.0:
        pass
    elif not (await services.config.guild(ctx.guild).reply_to_mentions_replies()):
        return await ctx.send("This command is not enabled.", ephemeral=True)

    try:
        await create_response(services, ctx)
    except Exception:
        logger.exception("Failed to generate response for slash command")
        await ctx.send(":warning: Error in generating response!", ephemeral=True)


@with_discord_log_context("message")
async def handle_message(services: "AIUserServices", message: discord.Message):
    """Handle regular message events"""
    ctx: commands.Context = await services.bot.get_context(message)

    if not (await is_valid_message(services, ctx)):
        return

    if await check_triggers(services, ctx, message):
        pass
    elif random.random() > await get_percentage(services, ctx):
        return

    if URL_PATTERN.search(ctx.message.content):
        ctx = await wait_for_embed(ctx)

    await create_response(services, ctx)


async def get_percentage(services: "AIUserServices", ctx: commands.Context) -> float:
    """Get reply percentage based on member/role/channel/guild settings"""
    percentage = await services.resolver.resolve_for_ctx("reply_percent", ctx)
    if percentage is None:
        percentage = DEFAULT_REPLY_PERCENT
    return percentage


async def wait_for_embed(ctx: commands.Context) -> commands.Context:
    """Wait for possible embed to be valid"""
    start_time = asyncio.get_event_loop().time()
    while not is_embed_valid(ctx.message):
        ctx.message = await ctx.channel.fetch_message(ctx.message.id)
        if asyncio.get_event_loop().time() - start_time >= 3:
            break
        await asyncio.sleep(1)
    return ctx
