import logging

from aiuser.functions.searxng.query import search_searxng
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import (Function, Parameters,
                                                  ToolCallSchema)
from aiuser.response.llm_pipeline import LLMPipeline

logger = logging.getLogger("red.bz_cogs.aiuser")


class SearXNGToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="searxng",
        description="Searches using the query for any unknown information or most current infomation",
        parameters=Parameters(
            properties={
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
            },
            required=["query"]
        )))
    function_name = schema.function.name

    async def _handle(self, request: LLMPipeline, arguments):
        """Handle the function call."""
        endpoint = await request.config.guild(self.ctx.guild).function_calling_searxng_url()
        results = await request.config.guild(self.ctx.guild).function_calling_searxng_max_results()
        logger.debug(f'Attempting SearXNG url {endpoint} in {self.ctx.guild}')
        return await search_searxng(arguments["query"], endpoint, results, self.ctx)
