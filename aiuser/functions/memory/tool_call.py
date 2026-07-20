import logging
from typing import Any, Dict, Optional

from redbot.core import commands

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.memory")


async def _canonical_scope_ids(
    ctx: commands.Context, user: Optional[str], channel: Optional[str]
):
    user_id = None
    channel_id = None

    if user:
        member = await commands.MemberConverter().convert(ctx, str(user))
        user_id = str(member.id)

    if channel:
        try:
            resolved_channel = await commands.GuildChannelConverter().convert(
                ctx, str(channel)
            )
        except commands.BadArgument:
            resolved_channel = await commands.ThreadConverter().convert(
                ctx, str(channel)
            )
        channel_id = str(resolved_channel.id)

    return user_id, channel_id


class SaveMemoryToolCall(ToolCall):
    function_name = names.SAVE_MEMORY
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Extract and reliably save an important fact about the user or context for long-term memory. Overwrite previous facts if they have changed or are outdated. Use this sparingly and store it as a concise but descriptive fact.",
            parameters=Parameters(
                properties={
                    "memory_name": {
                        "type": "string",
                        "description": "A short, unique, and descriptive name/topic for this memory fact (less than 30 characters).",
                    },
                    "memory_text": {
                        "type": "string",
                        "description": "The detailed fact to remember, written clearly.",
                    },
                    "user": {
                        "type": "string",
                        "description": "Optional: If this memory is specifically about a user, provide their username, mention, or Discord user ID.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional: If this memory is specifically about an ongoing event/context in a certain channel, provide its name, mention, or Discord channel ID.",
                    },
                },
                required=["memory_name", "memory_text"],
            ),
        )
    )

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        memory_name = arguments.get("memory_name")
        memory_text = arguments.get("memory_text")
        user = arguments.get("user")
        channel = arguments.get("channel")

        if not memory_name or not memory_text:
            return "Failed: Missing memory_name or memory_text"

        try:
            user, channel = await _canonical_scope_ids(tool_context.ctx, user, channel)
            guild_id = tool_context.ctx.guild.id
            db = tool_context.services.memories

            memory_id = await db.upsert(
                guild_id,
                memory_name,
                memory_text,
                user=user,
                channel=channel,
            )

            logger.info("Saved memory '%s'", memory_name)
            return f"Success: Saved memory with ID {memory_id}"
        except commands.BadArgument:
            return "Failed: Could not resolve the requested user or channel scope"
        except Exception:
            logger.exception("Failed to save memory")
            return "Failed: Internal error while saving memory"


class ReadMemoryToolCall(ToolCall):
    function_name = names.READ_MEMORY
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Search the long-term memory database for a specific fact or context. Use a concise search query.",
            parameters=Parameters(
                properties={
                    "search_query": {
                        "type": "string",
                        "description": "Keywords or a short phrase to search for in the memory database (e.g., 'user preference', 'past project').",
                    },
                    "user": {
                        "type": "string",
                        "description": "Optional: Only search memories related to this specific user, identified by username, mention, or Discord user ID.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional: Only search memories related to this specific channel name, mention, or Discord channel ID.",
                    },
                },
                required=["search_query"],
            ),
        )
    )

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        search_query = arguments.get("search_query")
        user = arguments.get("user")
        channel = arguments.get("channel")

        if not search_query:
            return "Failed: Missing search_query"

        try:
            user, channel = await _canonical_scope_ids(tool_context.ctx, user, channel)
            guild_id = tool_context.ctx.guild.id
            db = tool_context.services.memories

            memory_results = await db.search_similar(
                search_query, guild_id, k=3, user=user, channel=channel
            )

            if not memory_results:
                return "No relevant memories found for the given query."

            result_texts = []
            for name, text, _similarity in memory_results:
                result_texts.append(f"- [{name}]: {text}")

            formatted_results = "\n".join(result_texts)
            logger.info(
                f"Read memories for query '{search_query}' (guild_id={guild_id})"
            )
            return f"Found relevant memories:\n{formatted_results}"

        except commands.BadArgument:
            return "Failed: Could not resolve the requested user or channel scope"
        except Exception:
            logger.exception("Failed to read memory")
            return "Failed: Internal error while reading memory"
