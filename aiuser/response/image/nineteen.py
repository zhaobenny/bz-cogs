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
NINETEEN_API_URL = "https://api.nineteen.ai/v1/text-to-image"
NINETEEN = "sn19"


class NineteenGenerator(ImageGenerator):

    def __init__(self, ctx, config):
        self.ctx = ctx
        self.config = config
        self.bot = ctx.bot

    async def _get_api_key(self, provider: str):
        """Get the API key from shared API tokens."""
        return (await self.bot.get_shared_api_tokens(NINETEEN)).get("api_key")

    async def generate_image(self, caption):
        """Generate image using sn19.ai API."""

        api_key = await self._get_api_key(NINETEEN)
        if not api_key:
            raise ValueError("No API key set for sn19.ai")

        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        data = {
            "prompt": caption,
            "model": "flux-schnell-text-to-image",
            "steps": 20,
            "cfg_scale": 7.5,
            "height": 1024,
            "width": 1024,
            "negative_prompt": "nsfw, lowres, bad anatomy, bad hands, missing fingers, deformed_face, jpeg artifacts, signature, blurry, artist name, deformed",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                NINETEEN_API_URL, headers=headers, json=data
            ) as response:
                if response.status == 200:
                    res = await response.json()
                    image = io.BytesIO(base64.b64decode(res["image_b64"]))
                    return image
                else:
                    error_text = await response.text()
                    raise Exception(
                        f"sn19.ai API error: {response.status} - {error_text}"
                    )
