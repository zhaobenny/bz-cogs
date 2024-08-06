import asyncio
import base64
import io
import json
import logging
import random

import aiohttp
import perchance as pc
from PIL import Image
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_random

from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class PerchanceGenerator(ImageGenerator):
    async def generate_image(self, caption):
        # eg. https://perchance.org/ai-text-to-image-generator
        # requires "pip install perchance"

        url = await self.config.guild(self.ctx.guild).image_requests_endpoint()
        self.model = url.split("/")[-2]

        payload = await self._prepare_payload(caption)

        # print(
        #     f"URL: {url}, model: {self.model}, payload: {json.dumps(payload, indent=4)}"
        # )
        logger.debug(
            f"Sending SD request to Perchance with payload: {json.dumps(payload, indent=4)}"
        )

        await visit_and_close_url(
            "https://perchance.org/ai-text-to-image-generator"
        )  # Otherwise it's more prone to ratelimit you

        payload = await self._prepare_payload(caption)
        seed = "-1"

        enegative_prompt = payload.get("negative_prompt", "")
        negative_prompt = f"(worst quality, low quality:1.3), [input.negative], low-quality, deformed, text, poorly drawn, hilariously bad drawing, bad 3D render, {enegative_prompt}"
        guidance_scale = payload.get("cfg-scale", 7)

        eprompt = payload.get("prompt", "")
        prompt = (
            f"(anime art of {eprompt}:1.2), masterpiece, 4k, best quality, anime art"
        )
        shape = "portrait"
        gen = pc.ImageGenerator()

        retries = 5
        delay = 3
        for attempt in range(retries):
            try:
                async with await gen.image(
                    prompt,
                    negative_prompt=negative_prompt,
                    seed=seed,
                    shape=shape,
                    guidance_scale=guidance_scale,
                ) as result:
                    binary = await result.download()

                    # Debug step: Check if binary data is valid
                    if binary is None:
                        raise ValueError("Received empty binary data")

                    try:
                        image = Image.open(binary)
                    except Exception as e:
                        logger.debug(f"Error opening image: {e}")

                        return

                    image_buffer = io.BytesIO()
                    image.save(image_buffer, format="PNG")
                    image_buffer.seek(0)

                return image_buffer
            except pc.errors.ConnectionError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay)  # Wait before retrying
                    delay *= 2  # Exponential backoff
                else:
                    logger.debug(
                        f"Perchance API overloaded. Please try again in a few minutes.\n{e}"
                    )


async def visit_and_close_url(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            await response.text()  # Wait for the page to load

    @retry(
        wait=wait_random(min=3, max=5),
        stop=(stop_after_attempt(4) | stop_after_delay(300)),
        reraise=True,
    )
    async def poll_status(self, session: aiohttp.ClientSession):

        while True:
            async with session.get(
                f"https://perchance.org/ai-text-to-image-generator"
            ) as response:
                response.raise_for_status()

                status = await response.text()

                if status == "completed":
                    break

                if status == "failed":
                    raise Exception("Job failed")

            await asyncio.sleep(random.randint(2, 5))
