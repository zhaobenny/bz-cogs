import asyncio
import base64
import logging
import time
from io import BytesIO
from typing import Optional

import aiohttp
from PIL import Image

from aiuser.common.constants import IMAGE_RESOLUTION, IMAGE_TIMEOUT
from aiuser.prompts.common.messages_list import MessagesList
from aiuser.prompts.image.base import BaseImagePrompt

logger = logging.getLogger("red.bz_cogs.aiuser")


class AIHordeImagePrompt(BaseImagePrompt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _process_image(self, image: Image) -> Optional[MessagesList]:
        apikey = (await self.bot.get_shared_api_tokens("ai-horde")).get("api_key") or "0000000000"
        image = self.scale_image(image, IMAGE_RESOLUTION ** 2)
        image_bytes = BytesIO()
        image.convert('RGB').save(image_bytes, format='webp', exact=True)
        encoded_image = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
        author = self.message.author.nick or self.message.author.name

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
                session_id = response["id"]

                start_time = time.monotonic()
                while True:
                    request = await session.get(f"https://stablehorde.net/api/v2/interrogate/status/{session_id}")
                    if request.status != 200:
                        raise aiohttp.ClientResponseError(None, (), status=request.status)

                    response = await request.json()
                    if response["state"] == "done":
                        break

                    elapsed_time = time.monotonic() - start_time
                    if elapsed_time > IMAGE_TIMEOUT:
                        raise Exception("Request timed out")

                    await asyncio.sleep(1)

                caption = response["forms"][0]["result"]["caption"]
                logger.info(f"AI Horde image caption result: {caption}")
        except:
            logger.error(f"Failed scanning image using AI Horde", exc_info=True)
            return None

        caption_content = f'User "{author}" sent: [Image: {caption}]'
        await self.messages.add_msg(caption_content, self.message, force=True)
        self.cached_messages[self.message.id] = caption_content
        return self.messages
