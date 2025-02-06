
import base64
import io
import logging

from openai import AsyncOpenAI
from redbot.core import Config, commands

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class DalleImageGenerator(ImageGenerator):
    def __init__(self, ctx: commands.Context, config: Config, model: str, api_key: str):
        super().__init__(ctx, config)
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_image(self, caption):
        response = await self.client.images.generate(
            model=self.model,
            prompt=f"{await self.config.guild(self.ctx.guild).image_requests_preprompt()} {caption}",
            response_format="b64_json",
            n=1,
            size="1024x1024",
            quality="standard"
        )
        return io.BytesIO(base64.b64decode(response.data[0].b64_json))
