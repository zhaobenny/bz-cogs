from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import TYPE_CHECKING

import discord
from redbot.core import commands

from aiuser.context.converter.converter import MessageConverter
from aiuser.providers.llm.registry import get_llm_provider

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")

COMPACTION_PROMPT = """You are tasked with summarizing a segment of conversation.
You must combine the pre-existing summary of the conversation (if any) with the new messages provided below.
Provide a concise chronological summary that captures the essence of what was discussed, any important decisions, and relevant context.
Exclude noise, completely off-topic chitchat, and minor details. Keep the summary under 500 words.
"""


class CompactionManagerPhase(Enum):
    OPEN = auto()
    CLOSING = auto()
    CLOSED = auto()


class CompactionPhase(Enum):
    CHECKING = auto()
    RUNNING = auto()


class CompactionManager:
    def __init__(self, services: AIUserServices):
        self.services = services
        self.compaction_store = services.compaction_store
        self._compaction_phases: dict[int, CompactionPhase] = {}
        self.phase = CompactionManagerPhase.OPEN
        self._tasks: dict[int, asyncio.Task] = {}

    async def check_and_run_compaction(
        self, ctx: commands.Context, messages: list[discord.Message]
    ):
        """Check if compaction should run based on messages_backread threshold.

        Compaction triggers when the number of unsummarized messages reaches
        80% of the messages_backread limit. It summarizes the oldest 80% of
        those messages.
        """
        if (
            self.phase is not CompactionManagerPhase.OPEN
            or not self.compaction_store
            or not messages
        ):
            return

        compaction_enabled = await self.services.config.guild(
            ctx.guild
        ).compaction_enabled()
        if not compaction_enabled or self.phase is not CompactionManagerPhase.OPEN:
            return

        channel_id = ctx.channel.id
        if channel_id in self._compaction_phases:
            return
        # Claim before eligibility reads yield.
        self._compaction_phases[channel_id] = CompactionPhase.CHECKING
        try:
            messages_backread = await self.services.config.guild(
                ctx.guild
            ).messages_backread()
            last_compacted_id = (
                await self.compaction_store.get_last_compacted_message_id(
                    ctx.guild.id, channel_id
                )
            )
            if last_compacted_id:
                unsummarized = [m for m in messages if m.id > last_compacted_id]
            else:
                unsummarized = messages

            compaction_threshold = max(1, (messages_backread * 4 + 4) // 5)
            if len(unsummarized) < compaction_threshold:
                return
            compact_count = max(1, (len(unsummarized) * 4) // 5)
            to_compact = unsummarized[:compact_count]
            if self.phase is not CompactionManagerPhase.OPEN:
                return
            self._compaction_phases[channel_id] = CompactionPhase.RUNNING
            try:
                task = asyncio.create_task(self._run_compaction(ctx, to_compact))
                self._tasks[channel_id] = task
                task.add_done_callback(
                    lambda completed: self._task_done(channel_id, completed)
                )
            except BaseException:
                self._compaction_phases.pop(channel_id, None)
                raise
        finally:
            if self._compaction_phases.get(channel_id) is CompactionPhase.CHECKING:
                self._compaction_phases.pop(channel_id, None)

    def _task_done(self, channel_id: int, task: asyncio.Task):
        if self._tasks.get(channel_id) is task:
            self._tasks.pop(channel_id, None)
            if self._compaction_phases.get(channel_id) is CompactionPhase.RUNNING:
                self._compaction_phases.pop(channel_id, None)

    async def close(self):
        if self.phase is CompactionManagerPhase.CLOSED:
            return
        self.phase = CompactionManagerPhase.CLOSING
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.phase = CompactionManagerPhase.CLOSED

    async def _run_compaction(
        self, ctx: commands.Context, past_messages: list[discord.Message]
    ):
        try:
            guild_id = ctx.guild.id
            channel_id = ctx.channel.id

            existing_summary = await self.compaction_store.get_summary(
                guild_id, channel_id
            )

            converter = MessageConverter(self.services, ctx)
            new_msgs_text: list[str] = []

            # Format the messages block chronologically (oldest first)
            for msg in past_messages:
                converted = await converter.convert(msg)
                if not converted:
                    continue
                for entry in converted:
                    content = entry.content
                    if isinstance(content, list):
                        content = " ".join(
                            [
                                item.get("text", "")
                                for item in content
                                if isinstance(item, dict) and item.get("type") == "text"
                            ]
                        )
                    role = (
                        "Bot"
                        if entry.role == "assistant"
                        else ("User" if entry.role == "user" else "System")
                    )
                    new_msgs_text.append(f"[{role}] {content}")

            if not new_msgs_text:
                return

            new_messages_block = "\n".join(new_msgs_text)

            # Use custom prompt if configured, otherwise use default
            custom_prompt = await self.services.config.guild(
                ctx.guild
            ).custom_compaction_prompt()
            instructions = custom_prompt if custom_prompt else COMPACTION_PROMPT
            existing_summary_block = existing_summary or "(None)"
            prompt = f"""{instructions.strip()}

--- Existing Summary ---
{existing_summary_block}

--- New Messages to Summarize ---
{new_messages_block}
"""

            model = (
                await self.services.config.guild(ctx.guild).model()
                or await self.services.config.default_model()
            )

            provider = await get_llm_provider(self.services)
            if provider is None:
                logger.error("No LLM backend available for context compaction")
                return

            response = await provider.create_chat_step(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                kwargs={"max_tokens": 800},
            )

            new_summary = response.content
            if new_summary:
                # Record the newest message ID that was compacted
                newest_compacted_id = max(m.id for m in past_messages)
                await self.compaction_store.upsert_summary(
                    guild_id, channel_id, new_summary, newest_compacted_id
                )
                logger.debug(
                    f"Compacted {len(past_messages)} messages in channel {channel_id} "
                    f"(up to message {newest_compacted_id})."
                )

        except Exception:
            logger.exception(f"Failed to compact messages in channel {ctx.channel.id}")
        finally:
            self._compaction_phases.pop(ctx.channel.id, None)
