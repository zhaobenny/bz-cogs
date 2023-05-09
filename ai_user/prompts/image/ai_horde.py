import asyncio
import base64
import logging
import time
from io import BytesIO
from typing import Optional

import aiohttp
from PIL import Image
from redbot.core.bot import Red

from ai_user.constants import IMAGE_RESOLUTION
from ai_user.prompts.image.base import BaseImagePrompt

logger = logging.getLogger("red.bz_cogs.ai_user")


class AIHordeImagePrompt(BaseImagePrompt):
    def __init__(self, message, config, start_time, bot: Red):
        super().__init__(message, config, start_time)
        self.redbot = bot

    async def _process_image(self, image: Image, bot_prompt: str) -> Optional[list[dict[str, str]]]:
        apikey = (await self.redbot.get_shared_api_tokens("ai-horde")).get("api_key") or "0000000000"
        image = self.scale_image(image, IMAGE_RESOLUTION ** 2)
        image_bytes = BytesIO()
        image.convert('RGB').save(image_bytes, format='webp', exact=True)
        encoded_image = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
        payload = {
            "source_image": encoded_image,
            "slow_workers": True,
            "forms": [
                {
                    "name": "caption"
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                request = await session.post("https://stablehorde.net/api/v2/interrogate/async", json=payload, headers={"apikey": apikey})
                if request.status != 202:
                    raise aiohttp.ClientResponseError(None, (), status=request.status)

                response = await request.json()
                id = response["id"]

                start_time = time.monotonic()
                while True:
                    request = await session.get(f"https://stablehorde.net/api/v2/interrogate/status/{id}")
                    if request.status != 200:
                        raise aiohttp.ClientResponseError(None, (), status=response.status)

                    response = await request.json()
                    if response["state"] == "done":
                        break

                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time > 30:
                        raise Exception("Request timed out")

                    await asyncio.sleep(1)

                caption = response["forms"][0]["result"]["caption"]
        except:
            logger.error(
                f"Failed scanning image using AI Horde", exc_info=True)
            return None

        prompt = [
            {"role": "system", "content": f"{bot_prompt} \"{self.message.author.name}\" sent an image. Here is its description:"},
            {"role": "user", "content": caption},
        ]

        return prompt
