

import io
import logging

import discord
import httpx
import openai
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.response.chat.llm_pipeline import LLMPipeline

logger = logging.getLogger("red.bz_cogs.aiuser")


class ImageRequestToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="image_request",
        description="Generates a image of the providen description using AI. Use a highly detailed description.",
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
        description = arguments["description"]
        try:
            response = await request.openai_client.images.generate(
                model="dall-e-3",
                prompt=description,
                quality="standard",
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url

            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()

            image_data = io.BytesIO(response.content)
            image_data.seek(0)
            file = discord.File(image_data, filename="image.png")
            request.files_to_send.append(file)
        except (openai.BadRequestError, openai.APIError, httpx.RequestError) as e:
            logger.exception(f"Failed to get image for description: {description}", exc_info=e)
            return f"Failed to generate or retrieve the image. ({e.__class__.__name__})"

        return f"An image of \"{description}\" was generated and will be sent."
