import io
import logging
from typing import Optional

import discord

from aiuser.config.resolver import ScopedConfigResolver
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.response.llm_pipeline import LLMPipeline
from aiuser.utils.utilities import format_variables

from .providers.factory import PROVIDERS, detect_image_provider

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class ImageRequestToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="image_request",
            description="Generates or sents a image of the provided description and sends it to the chat.",
            parameters=Parameters(
                properties={
                    "description": {
                        "type": "string",
                        "description": "The description of the image to generate or send. Make it highly detailed.",
                    },
                },
                required=["description"],
            ),
        )
    )
    function_name = schema.function.name

    async def _handle(self, request: LLMPipeline, arguments):
        description = arguments["description"][:2000]
        preprompt = await self._pick_image_preprompt(request) or ""
        if preprompt:
            preprompt = await format_variables(request.ctx, preprompt)
            description = f"{preprompt} {description}"
        image_endpoint_override = await request.config.guild(
            request.ctx.guild
        ).function_calling_image_custom_endpoint()
        if image_endpoint_override:
            provider_endpoint = image_endpoint_override
        else:
            provider_endpoint = await request.config.custom_openai_endpoint()
        provider = detect_image_provider(provider_endpoint)
        try:
            gen_fn = PROVIDERS[provider]
            data = await gen_fn(description, request, image_endpoint_override)
            bio = io.BytesIO(data)
            bio.seek(0)
            request.files_to_send.append(discord.File(bio, filename="image.png"))
        except Exception as e:
            logger.exception(
                f"Failed to get image for description: {description[:500]}", exc_info=e
            )
            return "Couldn't generate an image..."
        return "The requested image was generated and was sent."

    async def _pick_image_preprompt(self, request: LLMPipeline) -> Optional[str]:
        """Select the image preprompt via member > role > channel > guild"""
        ctx = request.ctx
        return await ScopedConfigResolver(request.config).resolve(
            "function_calling_image_preprompt",
            guild=ctx.guild,
            channel=ctx.channel,
            member=ctx.message.author,
        )
