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
                },
                required=["memory_name", "memory_text"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        memory_name = arguments.get("memory_name")
        memory_text = arguments.get("memory_text")

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
            )

            logger.info(f"Saved memory '{memory_name}' for guild {guild_id}")
            return f"Success: Saved memory with ID {memory_id}"
        except Exception:
            logger.exception("Failed to save memory")
            return "Failed: Internal error while saving memory"
