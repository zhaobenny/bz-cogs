import logging
from typing import Any, Dict, Optional

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.searxng.query import search_searxng
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class SearXNGToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.SEARXNG,
            description="Searches using the query for any unknown information or most current infomation",
            parameters=Parameters(
                properties={
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                required=["query"],
            ),
        )
    )
    function_name = schema.function.name
    parallel_safe = True

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        """Handle the function call."""
        endpoint = await tool_context.services.config.guild(
            tool_context.ctx.guild
        ).function_calling_searxng_url()
        results = await tool_context.services.config.guild(
            tool_context.ctx.guild
        ).function_calling_searxng_max_results()
        logger.debug(f"Attempting SearXNG url {endpoint}")
        return await search_searxng(
            arguments["query"], endpoint, results, tool_context.ctx
        )
