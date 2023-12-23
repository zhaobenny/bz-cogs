import asyncio
import base64
import io
import json
import logging
import random

import aiohttp
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_random

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class NemusonaGenerator(ImageGenerator):
    async def generate_image(self, caption):
        # eg. https://waifus-api.nemusona.com/job/submit/nemu

        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        self.model = url.split("/")[-2]

        payload = await self._prepare_payload(caption)

        logger.debug(
            f"Sending SD request to Nemusona with payload: {json.dumps(payload, indent=4)}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'{url}', json=payload) as response:
                self.id = await response.text()
                if response.status != 201:
                    response.raise_for_status()

            await self.poll_status(session)

            async with session.get(f"https://waifus-api.nemusona.com/job/result/{self.model}/{self.id}") as response:
                if response.status != 200:
                    response.raise_for_status()
                r = await response.json()

        image = (io.BytesIO(base64.b64decode(r["base64"])))
        return image

    @retry(
        wait=wait_random(min=3, max=5), stop=(stop_after_attempt(4) | stop_after_delay(300)),
        reraise=True
    )
    async def poll_status(self, session: aiohttp.ClientSession):

        while True:
            async with session.get(f"https://waifus-api.nemusona.com/job/status/{self.model}/{self.id}") as response:
                if response.status != 200:
                    response.raise_for_status()

                status = await response.text()

                if status == "completed":
                    break

                if status == "failed":
                    raise Exception("Job failed")

            await asyncio.sleep(random.randint(2, 5))
