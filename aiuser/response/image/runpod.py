import base64
import io
import json
import logging

import aiohttp
from redbot.core import Config, commands
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_random

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class RunPodGenerator(ImageGenerator):
    STATUS_COMPLETED = 'COMPLETED'

    def __init__(self, ctx: commands.Context, config: Config, apikey: str):
        self.apikey = apikey
        super().__init__(ctx, config)

    async def _prepare_payload(self, caption):
        parameters = await self.config.guild(self.ctx.guild).image_requests_parameters()
        parameters = json.loads(parameters) if parameters else {}
        prompt = (
            await self.config.guild(self.ctx.guild).image_requests_preprompt()
            + " "
            + caption
        )
        parameters["prompt"] = prompt
        return {
            "input": {
                "api": {
                    "method": "POST",
                    "endpoint": "/sdapi/v1/txt2img"
                },
                "payload": parameters
            }
        }

    @retry(wait=wait_random(min=2, max=3), stop=stop_after_attempt(2) | stop_after_delay(190), reraise=True)
    async def generate_image(self, caption):
        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()

        if not "runsync" in url:
            raise Exception("Incompatible Runpod endpoint, use /runsync instead of /run")

        payload = await self._prepare_payload(caption)
        headers = {"Authorization": "Bearer " + self.apikey}

        logger.debug(
            f"Sending SD request to runpod-worker-a1111 Runpod with payload: {json.dumps(payload, indent=4)}")

        image = await self._post_request(url, headers, payload)

        return image

    async def _post_request(self, url, headers, payload):
        headers = {"Authorization": "Bearer " + self.apikey}
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, headers=headers, json=payload) as response:
                response.raise_for_status()

                response = await response.json()
                if response['status'] != self.STATUS_COMPLETED:
                    raise Exception(f"Invalid response from Runpod: {response['status']}")

                image_data = base64.b64decode(response["output"]["images"][0])

        return io.BytesIO(image_data)
