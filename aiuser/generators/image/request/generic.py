import base64
import io
import json
import logging

import aiohttp
from redbot.core import Config, commands
from tenacity import retry, stop_after_attempt, wait_random

from aiuser.generators.image.request.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class GenericStableDiffusionGenerator(ImageGenerator):
    def __init__(self, ctx: commands.Context, config: Config):
        super().__init__(ctx, config)

    @retry(
        wait=wait_random(min=2, max=5), stop=(stop_after_attempt(4)),
        reraise=True
    )
    async def generate_image(self, caption):
        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        parameters = await self.config.guild(self.ctx.guild).image_requests_parameters()
        payload = {}

        if parameters is not None:
            payload = json.loads(parameters)

        payload["prompt"] = await self.config.guild(self.ctx.guild).image_requests_preprompt() + " " + caption
        logger.debug(f"Sending SD request with payload: {json.dumps(payload, indent=4)}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'{url}', json=payload) as response:
                r = await response.json()
        image = (io.BytesIO(base64.b64decode(r['images'][0])))
        return image
