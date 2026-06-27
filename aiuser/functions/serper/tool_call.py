from typing import Any, Dict, Optional

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.serper.query import serper_search
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema


class SerperToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.SEARCH_GOOGLE,
            description="Searches Google using the query for any unknown information or most current infomation",
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
        return await serper_search(
            arguments["query"],
            (await self.bot.get_shared_api_tokens("serper")).get("api_key"),
            self.ctx,
        )
