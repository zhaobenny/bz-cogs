from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, List, Set

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


class CompactionManager:
    def __init__(self, services: "AIUserServices"):
        self.services = services
        self.compaction_store = services.compaction_store
        self._compaction_locks: Set[int] = set()

    async def check_and_run_compaction(
        self, ctx: commands.Context, messages: List[discord.Message]
    ):
        """Check if compaction should run based on messages_backread threshold.

        Compaction triggers when the number of unsummarized messages reaches
        80% of the messages_backread limit. It summarizes the oldest 80% of
        those messages.
        """
        if not self.compaction_store or not messages:
            return

        compaction_enabled = await self.services.config.guild(
            ctx.guild
        ).compaction_enabled()
        if not compaction_enabled:
            return

        channel_id = ctx.channel.id
        if channel_id in self._compaction_locks:
            return

        messages_backread = await self.services.config.guild(
            ctx.guild
        ).messages_backread()

        # Filter out messages that have already been compacted
        last_compacted_id = await self.compaction_store.get_last_compacted_message_id(
            ctx.guild.id, channel_id
        )
        if last_compacted_id:
            unsummarized = [m for m in messages if m.id > last_compacted_id]
        else:
            unsummarized = messages

        # Trigger when unsummarized messages reach 80% of the backread limit.
        compaction_threshold = max(1, (messages_backread * 4 + 4) // 5)
        if len(unsummarized) >= compaction_threshold:
            # Compact the oldest 80%
            compact_count = max(1, (len(unsummarized) * 4) // 5)
            to_compact = unsummarized[:compact_count]
            self._compaction_locks.add(channel_id)
            asyncio.create_task(self._run_compaction(ctx, to_compact))

    async def _run_compaction(
        self, ctx: commands.Context, past_messages: List[discord.Message]
    ):
        try:
            guild_id = ctx.guild.id
            channel_id = ctx.channel.id

            existing_summary = await self.compaction_store.get_summary(
                guild_id, channel_id
            )

            converter = MessageConverter(self.services, ctx)
            new_msgs_text: List[str] = []

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

            model = await self.services.config.guild(ctx.guild).model()

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
            self._compaction_locks.discard(ctx.channel.id)
