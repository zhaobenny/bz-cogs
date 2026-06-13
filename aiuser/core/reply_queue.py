from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import discord
from redbot.core import commands

from aiuser.config.constants import URL_PATTERN
from aiuser.config.defaults import (
    DEFAULT_MESSAGE_BURST_IDLE_SECONDS,
    DEFAULT_MESSAGE_BURST_MAX_SECONDS,
)
from aiuser.core.validators import is_valid_message
from aiuser.response.response import create_response
from aiuser.utils.utilities import wait_for_embed

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


BURST_MODE_RANDOM = "random"
BURST_MODE_CONVERSATION = "conversation"
BURST_MODE_PRIORITY = {
    BURST_MODE_RANDOM: 0,
    BURST_MODE_CONVERSATION: 1,
}

RESPONSE_KIND_DIRECT = "direct"
RESPONSE_KIND_BURST = "burst"


@dataclass
class ResponseRequest:
    kind: str
    channel_id: int
    message_id: int

    @classmethod
    def direct(cls, channel_id: int, message_id: int) -> "ResponseRequest":
        return cls(
            kind=RESPONSE_KIND_DIRECT,
            channel_id=channel_id,
            message_id=message_id,
        )

    @classmethod
    def message_burst(cls, channel_id: int, message_id: int) -> "ResponseRequest":
        return cls(
            kind=RESPONSE_KIND_BURST,
            channel_id=channel_id,
            message_id=message_id,
        )

    @property
    def is_direct(self) -> bool:
        return self.kind == RESPONSE_KIND_DIRECT


@dataclass
class MessageBurst:
    message_id: int
    percentage: float
    mode: str
    first_seen: float
    idle_seconds: float
    max_seconds: float
    task: Optional[asyncio.Task] = None

    def refresh(
        self,
        message_id: int,
        reply_chance: float,
        mode: str,
        idle_seconds: float,
        max_seconds: float,
    ):
        self.message_id = message_id
        self.idle_seconds = idle_seconds
        self.max_seconds = max_seconds

        if BURST_MODE_PRIORITY[mode] >= BURST_MODE_PRIORITY[self.mode]:
            self.mode = mode
            self.percentage = reply_chance

    def cancel_timer(self):
        if self.task and not self.task.done():
            self.task.cancel()


class ChannelReplyState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.message_burst: Optional[MessageBurst] = None
        self.queued_response: Optional[ResponseRequest] = None
        self.drain_task: Optional[asyncio.Task] = None

    def queue_response(self, request: ResponseRequest):
        previous = self.queued_response
        if previous is None:
            self.queued_response = request
            return

        if request.is_direct or not previous.is_direct:
            self.queued_response = request

    def pop_response(self) -> Optional[ResponseRequest]:
        request = self.queued_response
        self.queued_response = None
        return request

    def cancel_message_burst(self):
        burst = self.message_burst
        self.message_burst = None
        if burst:
            burst.cancel_timer()


def get_channel_reply_state(
    services: "AIUserServices", channel_id: int
) -> ChannelReplyState:
    state = services.reply_channel_states.get(channel_id)
    if state is None:
        state = ChannelReplyState()
        services.reply_channel_states[channel_id] = state
    return state


async def add_or_update_message_burst(
    services: "AIUserServices",
    ctx: commands.Context,
    reply_chance: float,
    mode: str,
):
    idle_seconds = await services.config.guild(ctx.guild).message_burst_idle_seconds()
    max_seconds = await services.config.guild(ctx.guild).message_burst_max_seconds()
    idle_seconds = idle_seconds or DEFAULT_MESSAGE_BURST_IDLE_SECONDS
    max_seconds = max_seconds or DEFAULT_MESSAGE_BURST_MAX_SECONDS

    now = asyncio.get_running_loop().time()
    state = get_channel_reply_state(services, ctx.channel.id)

    async with state.lock:
        burst = state.message_burst
        if burst is None:
            burst = MessageBurst(
                message_id=ctx.message.id,
                percentage=reply_chance,
                mode=mode,
                first_seen=now,
                idle_seconds=idle_seconds,
                max_seconds=max_seconds,
            )
            state.message_burst = burst
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
            close_message_burst_after(services, ctx.channel.id, burst)
        )


async def cancel_pending_message_burst(services: "AIUserServices", channel_id: int):
    state = get_channel_reply_state(services, channel_id)
    async with state.lock:
        state.cancel_message_burst()


async def close_message_burst_after(
    services: "AIUserServices", channel_id: int, burst: MessageBurst
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

    state = get_channel_reply_state(services, channel_id)
    async with state.lock:
        if state.message_burst is not burst:
            return
        state.message_burst = None
        burst.task = None

    if random.random() > burst.percentage:
        return

    await enqueue_response(
        services, ResponseRequest.message_burst(channel_id, burst.message_id)
    )


async def enqueue_response(services: "AIUserServices", request: ResponseRequest):
    state = get_channel_reply_state(services, request.channel_id)

    async with state.lock:
        state.queue_response(request)
        ensure_channel_drain_locked(services, request.channel_id, state)


def ensure_channel_drain_locked(
    services: "AIUserServices", channel_id: int, state: ChannelReplyState
):
    if state.drain_task and not state.drain_task.done():
        return
    state.drain_task = asyncio.create_task(
        drain_channel_responses(services, channel_id)
    )


async def drain_channel_responses(services: "AIUserServices", channel_id: int):
    state = get_channel_reply_state(services, channel_id)
    try:
        while True:
            async with state.lock:
                request = state.pop_response()

            if request is None:
                return

            await execute_response_request(services, request)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Unhandled error while draining aiuser response queue")
    finally:
        current_task = asyncio.current_task()
        async with state.lock:
            if state.drain_task is current_task:
                state.drain_task = None
            if state.queued_response is not None:
                ensure_channel_drain_locked(services, channel_id, state)


async def execute_response_request(
    services: "AIUserServices", request: ResponseRequest
) -> bool:
    ctx = await build_context_for_response_request(services, request)
    if ctx is None:
        return False

    try:
        if not (await is_valid_message(services, ctx)):
            return False

        if not ctx.interaction and URL_PATTERN.search(ctx.message.content):
            ctx = await wait_for_embed(ctx)

        return await create_response(services, ctx)
    except Exception:
        logger.exception("Error generating aiuser response")
        return False


async def build_context_for_response_request(
    services: "AIUserServices", request: ResponseRequest
) -> Optional[commands.Context]:
    channel = services.bot.get_channel(request.channel_id)
    if channel is None:
        return None

    try:
        message = await channel.fetch_message(request.message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None

    return await services.bot.get_context(message)


def cancel_reply_state_tasks(services: "AIUserServices"):
    for state in services.reply_channel_states.values():
        burst = state.message_burst
        if burst:
            burst.cancel_timer()
        if state.drain_task and not state.drain_task.done():
            state.drain_task.cancel()
    services.reply_channel_states.clear()
