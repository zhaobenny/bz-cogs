import logging
import asyncio
from typing import List

import discord
from redbot.core import commands

from aiuser.types.abc import MixinMeta
from aiuser.context.converter.converter import MessageConverter

logger = logging.getLogger("red.bz_cogs.aiuser")

COMPACTION_PROMPT = """You are tasked with summarizing a segment of conversation.
You must combine the pre-existing summary of the conversation (if any) with the new messages provided below.
Provide a concise chronological summary that captures the essence of what was discussed, any important decisions, and relevant context.
Exclude noise, completely off-topic chitchat, and minor details. Keep the summary under 500 words.

{existing_summary}

--- New Messages to Summarize ---
{new_messages}
"""


class CompactionManager:
    def __init__(self, cog: MixinMeta):
        self.cog = cog
        self.config = cog.config
        self.bot = cog.bot
        self.compaction_store = getattr(cog, "compaction_store", None)
        self._compaction_locks = set()

    async def check_and_run_compaction(
        self, ctx: commands.Context, messages: List[discord.Message]
    ):
        """Called periodically to check if the channel has exceeded the message trigger and run compaction in background."""
        if not self.compaction_store or not messages:
            return

        trigger_count = await self.config.guild(ctx.guild).compaction_trigger()
        if trigger_count <= 0:
            return

        channel_id = ctx.channel.id
        if channel_id in self._compaction_locks:
            return

        # Simple threshold check: if the list of uncompacted messages exceeds trigger
        # and we are not already compiling one
        if len(messages) >= trigger_count:
            self._compaction_locks.add(channel_id)
            asyncio.create_task(self._run_compaction(ctx, messages[:trigger_count]))

    async def _run_compaction(
        self, ctx: commands.Context, past_messages: List[discord.Message]
    ):
        try:
            guild_id = ctx.guild.id
            channel_id = ctx.channel.id

            existing_summary = await self.compaction_store.get_summary(
                guild_id, channel_id
            )

            formatted_existing = (
                f"--- Existing Summary ---\n{existing_summary}\n"
                if existing_summary
                else "--- Existing Summary ---\n(None)\n"
            )

            converter = MessageConverter(self.cog, ctx)
            new_msgs_text = []

            # Format the messages block chronologically (oldest first)
            for msg in reversed(past_messages):
                converted = await converter.convert(msg)
                if not converted:
                    continue
                # For simplicity, extract the text representation of each entry
                for entry in converted:
                    content = entry.content
                    # content can be string or list of dicts (vision)
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
            prompt = COMPACTION_PROMPT.format(
                existing_summary=formatted_existing, new_messages=new_messages_block
            )

            model = await self.config.guild(ctx.guild).model()

            response = await self.cog.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )

            new_summary = response.choices[0].message.content
            if new_summary:
                await self.compaction_store.upsert_summary(
                    guild_id, channel_id, new_summary
                )
                logger.debug(
                    f"Compacted {len(past_messages)} messages in channel {channel_id}."
                )

        except Exception:
            logger.exception(f"Failed to compact messages in channel {ctx.channel.id}")
        finally:
            self._compaction_locks.discard(ctx.channel.id)
