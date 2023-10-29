import asyncio
import base64
import io
import json
import logging
import random

import aiohttp
from redbot.core import Config, commands

from aiuser.generators.image.create.image_generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class NemusonaGenerator(ImageGenerator):
    def __init__(self, ctx: commands.Context, config: Config):
        super().__init__(ctx, config)

    async def generate_image(self, caption):
        # eg. https://waifus-api.nemusona.com/job/submit/nemu

        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        self.model = url.split("/")[-1]

        parameters = await self.config.guild(self.ctx.guild).image_requests_parameters()
        payload = {}

        if parameters is not None:
            payload = json.loads(parameters)

        payload["prompt"] = await self.config.guild(self.ctx.guild).image_requests_preprompt() + " " + caption
        logger.debug(f"Sending SD request to Nemusona with payload: {json.dumps(payload, indent=4)}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'{url}', json=payload) as response:
                self.id = await response.text()
                if response.status != 201:
                    raise Exception(f"Failed to create job {response.status}")

            await self.poll_status(session)

            async with session.get(f"https://waifus-api.nemusona.com/job/result/{self.model}/{self.id}") as response:
                if response.status != 200:
                    raise Exception(f"Failed to get job result {response.status}")
                r = await response.json()

        image = (io.BytesIO(base64.b64decode(r["base64"])))
        return image

    async def poll_status(self, session):
        start_time = asyncio.get_event_loop().time()

        while True:
            async with session.get(f"https://waifus-api.nemusona.com/job/status/{self.model}/{self.id}") as response:

                if response.status == 429:
                    raise Exception("Rate limited")

                if response.status != 200:
                    raise Exception(f"Failed to get job status {response.status}")

                status = await response.text()

                if status == "completed":
                    break

                if status == "failed":
                    raise Exception("Job failed")

            if asyncio.get_event_loop().time() - start_time >= 300:
                raise TimeoutError(f"Timed out after {300} seconds")

            await asyncio.sleep(random.randint(2, 5))
