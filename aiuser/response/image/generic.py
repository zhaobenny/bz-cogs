import base64
import io
import json
import logging

import aiohttp
from tenacity import retry, stop_after_attempt, wait_random

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class GenericImageGenerator(ImageGenerator):
    @retry(wait=wait_random(min=2, max=5), stop=stop_after_attempt(3), reraise=True)
    async def generate_image(self, caption):
        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        payload = await self._prepare_payload(caption)

        logger.debug(
            f"Sending SD request with payload: {json.dumps(payload, indent=4)}")
        image = await self._post_request(url, payload)
        return image

    async def _post_request(self, url, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, json=payload) as response:
                response.raise_for_status()
                r = await response.json()
                image_data = base64.b64decode(r["images"][0])

        return io.BytesIO(image_data)
