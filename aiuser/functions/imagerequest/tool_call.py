

import logging

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageRequestToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="image_request",
        description="Generates a image of the providen description using AI",
        parameters=Parameters(
            properties={
                "description": {
                    "type": "string",
                    "description": "The description of the image to generate",
                },
            },
            required=["description"]
        )))
    function_name = schema.function.name

    async def _handle(self, request, arguments):
        # request.
        return None
