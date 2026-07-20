"""Decides whether the bot replies to a message, and how."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, Optional

import discord
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_REPLY_PERCENT
from aiuser.core.decision.triggers import (
    check_direct_triggers,
    get_conversation_reply_chance,
)
from aiuser.core.decision.validators import is_valid_message

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


class BurstMode(IntEnum):
    RANDOM = 0
    CONVERSATION = 1


class ResponseKind(Enum):
    DIRECT = "direct"
    BURST = "burst"


@dataclass(frozen=True)
class ReplyDecision:
    kind: ResponseKind
    burst_mode: Optional[BurstMode] = None
    chance: float = 1.0


async def decide_response(
    services: "AIUserServices", ctx: commands.Context, message: discord.Message
) -> Optional[ReplyDecision]:
    """Will the bot reply to this message, and how?"""
    if not await is_valid_message(services, ctx):
        return None

    if await check_direct_triggers(services, ctx, message):
        return ReplyDecision(ResponseKind.DIRECT)

    chance = await get_conversation_reply_chance(services, ctx)
    if chance is not None:
        return ReplyDecision(ResponseKind.BURST, BurstMode.CONVERSATION, chance)

    chance = await get_percentage(services, ctx)
    if chance > 0:
        return ReplyDecision(ResponseKind.BURST, BurstMode.RANDOM, chance)

    return None


async def get_percentage(services: "AIUserServices", ctx: commands.Context) -> float:
    """Get reply percentage based on member/role/channel/guild settings"""
    percentage = await services.resolver.resolve_for_ctx("reply_percent", ctx)
    if percentage is None:
        percentage = DEFAULT_REPLY_PERCENT
    return percentage
