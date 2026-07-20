from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import discord
from redbot.core import commands

from aiuser.config.constants import URL_PATTERN
from aiuser.config.defaults import (
    DEFAULT_MESSAGE_BURST_IDLE_SECONDS,
    DEFAULT_MESSAGE_BURST_MAX_SECONDS,
)
from aiuser.core.decision import BurstMode, ResponseKind, is_valid_message
from aiuser.response.response import create_response
from aiuser.utils.utilities import wait_for_embed

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


@dataclass(frozen=True)
class ResponseRequest:
    kind: ResponseKind
    channel_id: int
    message_id: int
    include_latest_channel_context: bool = False


@dataclass
class MessageBurst:
    message_id: int
    percentage: float
    mode: BurstMode
    first_seen: float
    idle_seconds: float
    max_seconds: float
    task: Optional[asyncio.Task] = None

    def refresh(
        self,
        message_id: int,
        reply_chance: float,
        mode: BurstMode,
        idle_seconds: float,
        max_seconds: float,
    ):
        self.message_id = message_id
        self.idle_seconds = idle_seconds
        self.max_seconds = max_seconds

        if mode >= self.mode:
            self.mode = mode
            self.percentage = reply_chance

    def cancel_timer(self):
        if self.task and not self.task.done():
            self.task.cancel()


class ChannelReplyState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.message_burst: Optional[MessageBurst] = None
        self.pending_request: Optional[ResponseRequest] = None
        self.drain_task: Optional[asyncio.Task] = None
        self.is_executing = False
        self.last_bot_reply_at: Optional[datetime] = None
        self.llm_session_id: Optional[str] = None

    async def arm_burst(
        self,
        services: "AIUserServices",
        ctx: commands.Context,
        reply_chance: float,
        mode: BurstMode,
    ):
        idle_seconds = await services.config.guild(
            ctx.guild
        ).message_burst_idle_seconds()
        max_seconds = await services.config.guild(ctx.guild).message_burst_max_seconds()
        idle_seconds = idle_seconds or DEFAULT_MESSAGE_BURST_IDLE_SECONDS
        max_seconds = max_seconds or DEFAULT_MESSAGE_BURST_MAX_SECONDS

        now = asyncio.get_running_loop().time()
        async with self.lock:
            burst = self.message_burst
            if burst is None:
                burst = MessageBurst(
                    message_id=ctx.message.id,
                    percentage=reply_chance,
                    mode=mode,
                    first_seen=now,
                    idle_seconds=idle_seconds,
                    max_seconds=max_seconds,
                )
                self.message_burst = burst
            else:
                burst.cancel_timer()
                burst.refresh(
                    message_id=ctx.message.id,
                    reply_chance=reply_chance,
                    mode=mode,
                    idle_seconds=idle_seconds,
                    max_seconds=max_seconds,
                )

            burst.task = asyncio.create_task(
                self._close_burst_after(services, ctx.channel.id, burst)
            )

    async def cancel_pending_burst(self):
        async with self.lock:
            burst = self.message_burst
            self.message_burst = None
            if burst:
                burst.cancel_timer()

    async def _close_burst_after(
        self, services: "AIUserServices", channel_id: int, burst: MessageBurst
    ):
        now = asyncio.get_running_loop().time()
        delay = min(
            burst.idle_seconds,
            max(0, burst.first_seen + burst.max_seconds - now),
        )

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        async with self.lock:
            if self.message_burst is not burst:
                return
            self.message_burst = None
            burst.task = None

        if random.random() > burst.percentage:
            return

        await self.enqueue(
            services,
            ResponseRequest(
                kind=ResponseKind.BURST,
                channel_id=channel_id,
                message_id=burst.message_id,
            ),
        )

    async def enqueue(self, services: "AIUserServices", request: ResponseRequest):
        async with self.lock:
            if self.is_executing:
                if request.kind != ResponseKind.DIRECT:
                    return
                request = replace(request, include_latest_channel_context=True)

            previous = self.pending_request
            if (
                previous is None
                or previous.kind != ResponseKind.DIRECT
                or request.kind == ResponseKind.DIRECT
            ):
                # Burst replies should not displace a pending direct trigger.
                self.pending_request = request

            if self.drain_task is None or self.drain_task.done():
                self.drain_task = asyncio.create_task(
                    self._drain(services, request.channel_id)
                )

    async def _drain(self, services: "AIUserServices", channel_id: int):
        try:
            while True:
                async with self.lock:
                    request = self.pending_request
                    self.pending_request = None
                    if request is not None:
                        self.is_executing = True

                if request is None:
                    return

                try:
                    await execute_response_request(services, request)
                finally:
                    async with self.lock:
                        self.is_executing = False
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Unhandled error while draining aiuser response request queue"
            )
        finally:
            current_task = asyncio.current_task()
            async with self.lock:
                if self.drain_task is current_task:
                    self.drain_task = None
                if self.pending_request is not None:
                    self.drain_task = asyncio.create_task(
                        self._drain(services, channel_id)
                    )

    def cancel_tasks(self):
        burst = self.message_burst
        if burst:
            burst.cancel_timer()
        if self.drain_task and not self.drain_task.done():
            self.drain_task.cancel()


def get_or_create_channel_reply_state(
    services: "AIUserServices", channel_id: int
) -> ChannelReplyState:
    return services.reply_channel_states.setdefault(channel_id, ChannelReplyState())


async def execute_response_request(
    services: "AIUserServices", request: ResponseRequest
) -> bool:
    channel = services.bot.get_channel(request.channel_id)
    if channel is None:
        return False

    # gateway cache is kept up to date on edits/deletes, so prefer it over a REST call
    message = discord.utils.get(services.bot.cached_messages, id=request.message_id)
    if message is None:
        try:
            message = await channel.fetch_message(request.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False

    ctx = await services.bot.get_context(message)
    history_anchor = await get_latest_history_anchor(services, channel, request)

    try:
        if not (await is_valid_message(services, ctx)):
            return False

        if not ctx.interaction and URL_PATTERN.search(ctx.message.content):
            ctx = await wait_for_embed(ctx)

        return await create_response(services, ctx, history_anchor=history_anchor)
    except Exception:
        logger.exception("Error generating aiuser response")
        return False


async def get_latest_history_anchor(
    services: "AIUserServices", channel, request: ResponseRequest
) -> Optional[discord.Message]:
    if not request.include_latest_channel_context:
        return None

    message_id = getattr(channel, "last_message_id", None)
    if not message_id or message_id == request.message_id:
        return None

    cached = discord.utils.get(services.bot.cached_messages, id=message_id)
    if cached is not None:
        return cached

    try:
        return await channel.fetch_message(message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


def cancel_reply_state_tasks(services: "AIUserServices"):
    for state in services.reply_channel_states.values():
        state.cancel_tasks()
    services.reply_channel_states.clear()
