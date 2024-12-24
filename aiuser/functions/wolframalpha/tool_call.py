
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.functions.wolframalpha.query import ask_wolfram_alpha


class WolframAlphaFunctionCall(ToolCall):

    schema = ToolCallSchema(
        Function(
            name="ask_wolfram_alpha",
            description="Asks Wolfram Alpha about mathematical operations, unit conversions, or scientific questions.",
            parameters=Parameters(
                properties={
                    "query": {
                        "type": "string",
                        "description": "A math operation, unit conversion, or scientific questions"
                    }},
                required=["query"],
            )))
    function_name = schema.function.name

    async def _handle(self, arguments):
        return await ask_wolfram_alpha(arguments["query"], (await self.bot.get_shared_api_tokens("wolfram_alpha")).get("app_id"), self.ctx)
