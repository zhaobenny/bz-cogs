"""Entry points for message / slash-command events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_REPLY_PERCENT
from aiuser.core.reply_queue import (
    BurstMode,
    ResponseKind,
    ResponseRequest,
    get_channel_reply_state,
)
from aiuser.core.triggers import check_direct_triggers, get_conversation_reply_chance
from aiuser.core.validators import is_valid_message
from aiuser.response.response import create_response
from aiuser.utils.logging_context import with_discord_log_context

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
    if message.author.id == services.bot.user.id:
        if not message.embeds:
            state = get_channel_reply_state(services, message.channel.id)
            state.last_bot_reply_at = message.created_at
        return

    ctx: commands.Context = await services.bot.get_context(message)

    if not (await is_valid_message(services, ctx)):
        return

    if await check_direct_triggers(services, ctx, message):
        state = get_channel_reply_state(services, ctx.channel.id)
        await state.cancel_pending_burst()
        await state.enqueue(
            services,
            ResponseRequest(
                kind=ResponseKind.DIRECT,
                channel_id=ctx.channel.id,
                message_id=message.id,
            ),
        )
        return

    conversation_reply_chance = await get_conversation_reply_chance(services, ctx)
    if conversation_reply_chance is not None:
        state = get_channel_reply_state(services, ctx.channel.id)
        await state.arm_burst(
            services, ctx, conversation_reply_chance, BurstMode.CONVERSATION
        )
        return

    reply_chance = await get_percentage(services, ctx)
    if reply_chance <= 0:
        return

    state = get_channel_reply_state(services, ctx.channel.id)
    await state.arm_burst(services, ctx, reply_chance, BurstMode.RANDOM)


async def get_percentage(services: "AIUserServices", ctx: commands.Context) -> float:
    """Get reply percentage based on member/role/channel/guild settings"""
    percentage = await services.resolver.resolve_for_ctx("reply_percent", ctx)
    if percentage is None:
        percentage = DEFAULT_REPLY_PERCENT
    return percentage
