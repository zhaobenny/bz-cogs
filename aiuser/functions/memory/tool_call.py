import time
from typing import Any, Dict, List

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema


class CreateMemoryTool(ToolCall):
    function_name = "create_memory"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Adds a new memory to the long-term memory database.",
            parameters=Parameters(
                properties={
                    "memory_name": {
                        "type": "string",
                        "description": "A short name or title for the memory.",
                    },
                    "memory_text": {
                        "type": "string",
                        "description": "The detailed content of the memory to be stored.",
                    },
                },
                required=["memory_name", "memory_text"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        if not request.cog.db:
            return "Memory database is not available."

        memory_name = arguments.get("memory_name")
        memory_text = arguments.get("memory_text")

        try:
            rowid = await request.cog.db.create_memory(
                request.ctx.guild.id, memory_name, memory_text, int(time.time())
            )
            return f"Memory created successfully with ID {rowid}."
        except Exception as e:
            return f"Failed to create memory: {e}"


class EditMemoryTool(ToolCall):
    function_name = "edit_memory"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Edits an existing memory by its ID.",
            parameters=Parameters(
                properties={
                    "rowid": {
                        "type": "integer",
                        "description": "The ID of the memory to edit.",
                    },
                    "memory_name": {
                        "type": "string",
                        "description": "The new name for the memory.",
                    },
                    "memory_text": {
                        "type": "string",
                        "description": "The new content for the memory.",
                    },
                },
                required=["rowid", "memory_name", "memory_text"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        if not request.cog.db:
            return "Memory database is not available."

        rowid = arguments.get("rowid")
        memory_name = arguments.get("memory_name")
        memory_text = arguments.get("memory_text")

        try:
            await request.cog.db.update_memory(
                rowid, request.ctx.guild.id, memory_name, memory_text, int(time.time())
            )
            return f"Memory with ID {rowid} updated successfully."
        except Exception as e:
            return f"Failed to update memory: {e}"


class SearchMemoryTool(ToolCall):
    function_name = "search_memory"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Searches for memories similar to the query.",
            parameters=Parameters(
                properties={
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant memories.",
                    },
                },
                required=["query"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        if not request.cog.db:
            return "Memory database is not available."

        query = arguments.get("query")

        try:
            results = await request.cog.db.search_similar(
                query, request.ctx.guild.id, k=5
            )
            if not results:
                return "No relevant memories found."

            response = "Found the following memories:\n"
            for rowid, name, text, score in results:
                response += f"ID: {rowid}, Name: {name}, Content: {text} (Score: {score:.2f})\n"
            return response
        except Exception as e:
            return f"Failed to search memory: {e}"


class DeleteMemoryTool(ToolCall):
    function_name = "delete_memory"
    schema = ToolCallSchema(
        function=Function(
            name=function_name,
            description="Deletes a memory by its ID.",
            parameters=Parameters(
                properties={
                    "rowid": {
                        "type": "integer",
                        "description": "The ID of the memory to delete.",
                    },
                },
                required=["rowid"],
            ),
        )
    )

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        if not request.cog.db:
            return "Memory database is not available."

        rowid = arguments.get("rowid")

        try:
            success = await request.cog.db.delete_memory_by_id(
                rowid, request.ctx.guild.id
            )
            if success:
                return f"Memory with ID {rowid} deleted successfully."
            else:
                return f"Memory with ID {rowid} not found."
        except Exception as e:
            return f"Failed to delete memory: {e}"
