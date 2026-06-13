import logging

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class NoResponseToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.DO_NOT_RESPOND,
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

    async def _handle(self, tool_context: ToolContext, arguments):
        if arguments["respond"]:
            return "Will respond to the message"
        tool_context.suppress()
        logger.debug(f'Decided to not respond because: "{arguments["reason"]}"')
        return f"Decided to not respond because: {arguments['reason']}"
