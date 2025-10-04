

import io
import logging

import discord

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.response.llm_pipeline import LLMPipeline

from .providers.factory import PROVIDERS, detect_provider

logger = logging.getLogger("red.bz_cogs.aiuser")

class ImageRequestToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="image_request",
        description="Generates a image of the provided description using AI and sends it to the chat.",
        parameters=Parameters(
            properties={
                "description": {
                    "type": "string",
                    "description": "The description of the image to generate. Make it highly detailed.",
                },
            },
            required=["description"]
        )))
    function_name = schema.function.name

    async def _handle(self, request: LLMPipeline, arguments):
        description = arguments["description"][:2000]  
        preprompt = await request.config.guild(request.ctx.guild).function_calling_image_preprompt() or ""
        if preprompt:
            description = f"{preprompt} {description}"
        endpoint = await request.config.guild(request.ctx.guild).function_calling_image_custom_endpoint() or None
        provider = detect_provider(endpoint, request.openai_client)
        try:
            gen_fn = PROVIDERS[provider]
            data = await gen_fn(description, request, endpoint)
            bio = io.BytesIO(data)
            bio.seek(0)
            request.files_to_send.append(discord.File(bio, filename="image.png"))
        except Exception as e:
            logger.exception(f"Failed to get image for description: {description[:500]}", exc_info=e)
            return "Couldn't generate an image..."
        return "The requested image was generated and was sent."
