import logging

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class NoResponseToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="do_not_respond",
            description="Choose to not respond to the messages, by ignoring the conversation",
            parameters=Parameters(
                properties={
                    "reason": {
                        "type": "string",
                        "description": "The reason for the decision to not respond",
                    },
                    "respond": {
                        "type": "boolean",
                        "description": "Whether or not to not respond to the message",
                    },
                },
                required=["reason", "respond"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(self, request, arguments):
        if arguments["respond"]:
            return "Will respond to the message"
        request.suppress_response = True
        logger.debug(f'Decided to not respond because: "{arguments["reason"]}"')
        return f"Decided to not respond because: {arguments['reason']}"
