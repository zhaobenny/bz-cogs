import logging
from typing import Any, Dict, Optional

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.search.providers import PROVIDERS
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class SearchToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.SEARCH_WEB,
            description="Searches the web using the query for any unknown information or most current information",
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
        provider = await tool_context.services.config.guild(
            tool_context.ctx.guild
        ).function_calling_search_provider()
        search = PROVIDERS.get(provider)
        if not search:
            logger.warning(f"Unknown search provider {provider!r} configured")
            return "An error occured while searching."
        return await search(arguments["query"], tool_context)
