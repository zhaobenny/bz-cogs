import io
import json
import logging

import aiohttp
from redbot.core import Config, commands
from tenacity import retry, stop_after_attempt, wait_random

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class ModalImageGenerator(ImageGenerator):
    """
        This is specific to the serverless-img-gen Modal app
    """

    def __init__(self, ctx: commands.Context, config: Config, token: str):
        self.token = token or "a-good-auth-token"
        super().__init__(ctx, config)

    @retry(wait=wait_random(min=2, max=5), stop=stop_after_attempt(2), reraise=True)
    async def generate_image(self, caption):
        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        payload = await self._prepare_payload(caption)

        logger.debug(
            f"Sending request to serverless-img-gen Modal app with payload: {json.dumps(payload, indent=4)}")
        image = await self._post_request(url, payload)
        return image

    async def _post_request(self, url, payload):
        headers = {"Authorization": "Bearer " + self.token}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, headers=headers, json=payload) as response:
                image_data = await response.read()

        return io.BytesIO(image_data)
