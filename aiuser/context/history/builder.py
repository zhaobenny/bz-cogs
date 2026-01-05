import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List

import discord

from aiuser.context.consent.manager import CONSENT_EMBED_TITLE

if TYPE_CHECKING:
    from aiuser.context.messages import MessagesThread

logger = logging.getLogger("red.bz_cogs.aiuser")


class HistoryBuilder:
    def __init__(self, messages_list: "MessagesThread"):
        self.messages_list = messages_list
        self.config = messages_list.config
        self.guild = messages_list.guild
        self.consent_manager = messages_list.consent_manager
        self.bot = messages_list.bot
        self.init_message = messages_list.init_message
        self.start_time = messages_list.start_time
        self.cached_tool_calls = messages_list.cached_tool_calls

    async def build_history(self):
        """Add historical messages to the conversation context."""
        limit = await self.config.guild(self.guild).messages_backread()
        max_seconds_gap = await self.config.guild(
            self.guild
        ).messages_backread_seconds()
        start_time: datetime = (
            self.start_time - timedelta(seconds=1) if self.start_time else None
        )

        past_messages = await self._get_past_messages(limit, start_time)
        if not past_messages:
            return

        if not await self._is_valid_time_gap(
            self.init_message, past_messages[0], max_seconds_gap
        ):
            return

        users = await self.consent_manager.get_unknown_consent_users(past_messages[:10])

        await self._process_past_messages(past_messages, max_seconds_gap)

        if await self.consent_manager.should_send_consent_embed(users):
            await self.consent_manager.send_consent_embed(
                self.init_message.channel, users
            )

    async def _get_past_messages(
        self, limit: int, start_time: datetime
    ) -> List[discord.Message]:
        """Retrieve past messages from the channel."""
        return [
            message
            async for message in self.init_message.channel.history(
                limit=limit + 1,
                before=self.init_message,
                after=start_time,
                oldest_first=False,
            )
        ]

    async def _process_past_messages(
        self, past_messages: List[discord.Message], max_seconds_gap: int
    ):
        """Process and add past messages to the conversation context."""
        for i in range(len(past_messages) - 1):
            if self.messages_list.tokens > self.messages_list.token_limit:
                return logger.debug(
                    f"{self.messages_list.tokens} tokens used - nearing limit, "
                    f"stopping context creation for message {self.init_message.id}"
                )

            # Skip consent embeds
            if (
                past_messages[i].author.id == self.bot.user.id
                and past_messages[i].embeds
                and past_messages[i].embeds[0].title == CONSENT_EMBED_TITLE
            ):
                continue

            if await self._is_valid_time_gap(
                past_messages[i], past_messages[i + 1], max_seconds_gap
            ):
                await self.messages_list.add_discord_message(past_messages[i])
            else:
                await self.messages_list.add_discord_message(past_messages[i])
                break

            if past_messages[i].author.id == self.bot.user.id:
                await self._inject_cached_tool_calls(past_messages[i])

    async def _inject_cached_tool_calls(self, bot_message: discord.Message):
        """Inject possible cached tool call entries before a assistant response."""
        cache_key = (bot_message.channel.id, bot_message.id)
        cached_entries = self.cached_tool_calls[cache_key]
        if not cached_entries:
            return

        # Insert cached entries at start (stack-based build)
        # We process in reverse order so the first entry ends up at index 0
        for entry in reversed(cached_entries):
            if entry.role == "assistant":
                await self.messages_list.add_assistant_message(
                    content=entry.content, index=0, tool_calls=entry.tool_calls
                )
            elif entry.role == "tool":
                await self.messages_list.add_tool_result_message(
                    content=entry.content, tool_call_id=entry.tool_call_id, index=0
                )

    @staticmethod
    async def _is_valid_time_gap(
        message: discord.Message, next_message: discord.Message, max_seconds_gap: int
    ) -> bool:
        """Check if the time gap between messages is within the allowed range."""
        seconds_diff = abs(message.created_at - next_message.created_at).total_seconds()
        if seconds_diff > max_seconds_gap:
            return False
        return True
