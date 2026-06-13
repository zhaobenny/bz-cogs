import io
import logging
from typing import Optional

import discord

from aiuser.config.resolver import ScopedConfigResolver
from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.utils.utilities import format_variables

from .providers.factory import PROVIDERS, detect_image_provider

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


class ImageRequestToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.IMAGE_REQUEST,
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

    async def _handle(self, tool_context: ToolContext, arguments):
        description = arguments["description"][:2000]
        preprompt = await self._pick_image_preprompt() or ""
        if preprompt:
            preprompt = await format_variables(self.ctx, preprompt)
            description = f"{preprompt} {description}"

        image_endpoint_override = await self.config.guild(
            self.ctx.guild
        ).function_calling_image_custom_endpoint()
        if image_endpoint_override:
            provider_endpoint = image_endpoint_override
        else:
            provider_endpoint = await self.config.custom_openai_endpoint()

        provider = detect_image_provider(provider_endpoint)
        try:
            gen_fn = PROVIDERS[provider]
            data = await gen_fn(description, tool_context, image_endpoint_override)
            bio = io.BytesIO(data)
            bio.seek(0)
            tool_context.attach_file(discord.File(bio, filename="image.png"))
        except Exception as e:
            logger.exception(
                f"Failed to get image for description: {description[:500]}", exc_info=e
            )
            return "Couldn't generate an image..."
        return "The requested image was generated and was sent."

    async def _pick_image_preprompt(self) -> Optional[str]:
        """Select the image preprompt via member > role > channel > guild"""
        return await ScopedConfigResolver(self.config).resolve(
            "function_calling_image_preprompt",
            guild=self.ctx.guild,
            channel=self.ctx.channel,
            member=self.ctx.message.author,
        )
