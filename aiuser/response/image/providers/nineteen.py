import base64
import io
import logging

import aiohttp

from aiuser.response.image.providers.generator import ImageGenerator

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

        payload = await self._prepare_payload(caption)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                NINETEEN_API_URL, headers=headers, json=payload
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
