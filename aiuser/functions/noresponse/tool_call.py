

import logging

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import (Function, Parameters,
                                                  ToolCallSchema)

logger = logging.getLogger("red.bz_cogs.aiuser")


class NoResponseToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
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
                    "description": "Whether or not to not respond",
                }
            },
            required=["reason", "respond"]
        )))
    function_name = schema.function.name

    async def _handle(self, arguments):
        if arguments["respond"]:
            return None

        request = arguments["request"]
        request.completion = ""
        logger.debug(f"Decided to not respond in guild {self.ctx.guild.id} because: \"{arguments['reason']}\"")
        return None
