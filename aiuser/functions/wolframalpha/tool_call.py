from __future__ import annotations

from typing import Any

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.functions.wolframalpha.query import ask_wolfram_alpha


class WolframAlphaFunctionCall(ToolCall):
    schema = ToolCallSchema(
        Function(
            name=names.ASK_WOLFRAM_ALPHA,
            description="Asks Wolfram Alpha about mathematical operations, unit conversions, or scientific questions.",
            parameters=Parameters(
                properties={
                    "query": {
                        "type": "string",
                        "description": "A math operation, unit conversion, or scientific questions",
                    }
                },
                required=["query"],
            ),
        )
    )
    function_name = schema.function.name
    parallel_safe = True

    async def _handle(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str | None:
        return await ask_wolfram_alpha(
            arguments["query"],
            (
                await tool_context.services.bot.get_shared_api_tokens("wolfram_alpha")
            ).get("app_id"),
            tool_context.ctx,
        )
