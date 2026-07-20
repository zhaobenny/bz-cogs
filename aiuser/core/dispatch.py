"""Wires message / slash-command events to reply decisions and the reply queue."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from redbot.core import commands

from aiuser.core.decision import (
    ResponseKind,
    decide_response,
    get_percentage,
    is_valid_message,
)
from aiuser.core.reply_queue import ResponseRequest, get_or_create_channel_reply_state
from aiuser.response import build_and_respond
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

    get_or_create_channel_reply_state(services, ctx.channel.id)
    try:
        await build_and_respond(services, ctx)
    except Exception:
        logger.exception("Failed to generate response for slash command")
        await ctx.send(":warning: Error in generating response!", ephemeral=True)


@with_discord_log_context("message")
async def handle_message(services: "AIUserServices", message: discord.Message):
    """Handle regular message events"""
    if message.author.id == services.bot.user.id:
        return

    ctx: commands.Context = await services.bot.get_context(message)

    decision = await decide_response(services, ctx, message)
    if decision is None:
        return

    state = get_or_create_channel_reply_state(services, ctx.channel.id)
    if decision.kind is ResponseKind.DIRECT:
        await state.cancel_pending_burst()
        await state.enqueue(
            services,
            ResponseRequest(
                kind=ResponseKind.DIRECT,
                channel_id=ctx.channel.id,
                message_id=message.id,
            ),
        )
    else:
        await state.arm_burst(services, ctx, decision.chance, decision.burst_mode)
