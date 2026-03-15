import logging
import time
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser")


class SaveMemoryToolCall(ToolCall):
    function_name = "save_memory"
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
                        "description": "Optional: If this memory is specifically about a user, provide their Username or UserID.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional: If this memory is specifically about an ongoing event/context in a certain channel, provide the channel name or ID.",
                    },
                },
                required=["memory_name", "memory_text"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        memory_name = arguments.get("memory_name")
        memory_text = arguments.get("memory_text")
        user = arguments.get("user")
        channel = arguments.get("channel")

        if not memory_name or not memory_text:
            return "Failed: Missing memory_name or memory_text"

        try:
            current_timestamp = int(time.time())
            guild_id = self.ctx.guild.id
            db = request.cog.db

            memory_id = await db.upsert(
                guild_id,
                memory_name,
                memory_text,
                current_timestamp,
                user=user,
                channel=channel,
            )

            logger.info(f"Saved memory '{memory_name}' for guild {guild_id}")
            return f"Success: Saved memory with ID {memory_id}"
        except Exception:
            logger.exception("Failed to save memory")
            return "Failed: Internal error while saving memory"


class ReadMemoryToolCall(ToolCall):
    function_name = "read_memory"
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
                        "description": "Optional: Only search memories related to this specific user (Username or UserID).",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Optional: Only search memories related to this specific channel name or ID.",
                    },
                },
                required=["search_query"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        search_query = arguments.get("search_query")
        user = arguments.get("user")
        channel = arguments.get("channel")

        if not search_query:
            return "Failed: Missing search_query"

        try:
            guild_id = self.ctx.guild.id
            db = request.cog.db

            memory_results = await db.search_similar(
                search_query, guild_id, k=3, user=user, channel=channel
            )

            if not memory_results:
                return "No relevant memories found for the given query."

            result_texts = []
            for name, text, _similarity in memory_results:
                result_texts.append(f"- [{name}]: {text}")

            formatted_results = "\n".join(result_texts)
            logger.info(f"Read memories for query '{search_query}' in guild {guild_id}")
            return f"Found relevant memories:\n{formatted_results}"

        except Exception:
            logger.exception("Failed to read memory")
            return "Failed: Internal error while reading memory"
