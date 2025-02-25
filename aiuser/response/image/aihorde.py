
import logging
from io import BytesIO
from typing import Optional

import aiohttp
from redbot.core import Config, commands
from tenacity import retry, stop_after_delay, wait_random

from aiuser.config.constants import IMAGE_REQUEST_AIHORDE_URL
from aiuser.response.image.generator import ImageGenerator

logger = logging.getLogger("red.bz_cogs.aiuser")


class AIHordeGenerator(ImageGenerator):
    def __init__(self, ctx: commands.Context, config: Config, api_key: Optional[str]):
        super().__init__(ctx, config)
        self.headers = {'apikey': api_key or "0000000000"}

    async def generate_image(self, caption):
        payload = await self._prepare_payload(caption)
        async with aiohttp.ClientSession() as session:
            res = await session.post(f"{IMAGE_REQUEST_AIHORDE_URL}/v2/generate/async", headers=self.headers, json=payload)
            if res.status == 400:
                res = await res.json()
                raise ValueError(f"{res['message']}: `{str(res.get('errors'))}`")

            res.raise_for_status()

            res = await res.json()
            logger.debug("AI Horde inital response: %s", res)
            uuid = res["id"]
            await self._wait_for_image(session, uuid)
            res = await self._get_image(session, uuid)
            image = BytesIO(await (await session.get(res['img'])).read())
            return image

    async def _wait_for_image(self, session: aiohttp.ClientSession, uuid: str):
        await self._check_image_done_with_retry(session, uuid)

    @retry(stop=stop_after_delay(60 * 10), wait=wait_random(min=5, max=9), reraise=True)
    async def _check_image_done_with_retry(self, session: aiohttp.ClientSession, uuid: str):
        if await self._check_image_done(session, uuid):
            return True
        raise aiohttp.ClientError(f"Image {uuid} is not ready yet.")

    async def _check_image_done(self, session: aiohttp.ClientSession, uuid: str):
        res = await session.get(f"{IMAGE_REQUEST_AIHORDE_URL}/v2/generate/check/{uuid}", headers=self.headers)
        res.raise_for_status()
        res = await res.json()
        return res["done"] == True

    async def _get_image(self, session: aiohttp.ClientSession, uuid: str):
        res = await session.get(f"{IMAGE_REQUEST_AIHORDE_URL}/v2/generate/status/{uuid}", headers=self.headers)
        res.raise_for_status()
        res = await res.json()
        return res["generations"][0]
