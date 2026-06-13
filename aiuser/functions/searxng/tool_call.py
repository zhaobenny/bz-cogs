import logging

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

    async def _handle(self, tool_context: ToolContext, arguments):
        """Handle the function call."""
        endpoint = await self.config.guild(
            self.ctx.guild
        ).function_calling_searxng_url()
        results = await self.config.guild(
            self.ctx.guild
        ).function_calling_searxng_max_results()
        logger.debug(f"Attempting SearXNG url {endpoint}")
        return await search_searxng(arguments["query"], endpoint, results, self.ctx)
