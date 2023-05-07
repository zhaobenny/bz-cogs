import base64
import logging
import time
import aiohttp
from io import BytesIO
from typing import Optional
from PIL import Image
from redbot.core.bot import Red

from ai_user.prompts.image_prompt.base import BaseImagePrompt
from ai_user.prompts.constants import IMAGE_DIMENSIONS

logger = logging.getLogger("red.bz_cogs.ai_user")


class AIHordeImagePrompt(BaseImagePrompt):
    def __init__(self, message, config, start_time, bot: Red):
        super().__init__(message, config, start_time)
        self.redbot = bot

    async def _process_image(self, image: Image, bot_prompt: str) -> Optional[list[dict[str, str]]]:
        apikey = (await self.redbot.get_shared_api_tokens("ai-horde")).get("api_key") or "0000000000"
        image_bytes = BytesIO()
        if any(size > IMAGE_DIMENSIONS for size in image.size):
            hsize = int((float(image.size[1]) * float(IMAGE_DIMENSIONS / float(image.size[0]))))
            image = image.resize((IMAGE_DIMENSIONS, hsize), Image.Resampling.LANCZOS)
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
                request = await session.post(f"https://stablehorde.net/api/v2/interrogate/async", json=payload, headers={"apikey": apikey})
                if request.status != 202:
                    raise aiohttp.ClientResponseError(None, (), status=request.status)

                response = await request.json()
                id = response["id"]

                start_time = time.time()
                while True:
                    request = await session.get(f"https://stablehorde.net/api/v2/interrogate/status/{id}")
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    if request.status != 200:
                        raise aiohttp.ClientResponseError(None, (), status=response.status)
                    elif elapsed_time > 30:
                        raise Exception("Request timed out")
                    response = await request.json()
                    if response["state"] == "done":
                        break
                caption = response["forms"][0]["result"]
        except:
            logger.error(
                f"Failed scanning image using AI Horde", exc_info=True)
            return None

        prompt = [
            {"role": "system", "content": f"The following is a description of a picture sent by user \"{self.message.author.name}\". {bot_prompt}"},
            {"role": "user", "content": caption["caption"]},
        ]

        return prompt
