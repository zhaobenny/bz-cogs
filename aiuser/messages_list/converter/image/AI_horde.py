

import asyncio
import base64
import logging
import random
from io import BytesIO

import aiohttp
from discord import Message
from PIL.Image import Image
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_random

from aiuser.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def process_image_ai_horde(cog: MixinMeta, message: Message, image: Image):
    api_key = (await cog.bot.get_shared_api_tokens("ai-horde")).get("api_key") or "0000000000"
    buffer = BytesIO()
    image.convert('RGB').save(buffer, format='webp', exact=True)
    encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
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
        caption = await request_ai_horde(payload, api_key)
    except:
        logger.exception(f"Failed request to AI Horde")

    logger.info(
        f"AI Horde image caption result for message {message.id} in {message.guild.name}: {caption}")

    if not caption:
        return None

    content = f'User "{message.author.display_name}" sent: [Image: {caption}]'
    return content


async def request_ai_horde(payload, api_key):
    async with aiohttp.ClientSession() as session:
        async with session.post("https://stablehorde.net/api/v2/interrogate/async", json=payload, headers={"apikey": api_key}) as response:
            if response.status != 202:
                response.raise_for_status()

            response = await response.json()
            session_id = response["id"]

            response = await wait_for_response(session, session_id)

            caption = response["forms"][0]["result"]["caption"]
            return caption


@retry(
    wait=wait_random(min=1, max=3), stop=(stop_after_attempt(4) | stop_after_delay(300)),
    reraise=True
)
async def wait_for_response(session: aiohttp.ClientSession, session_id):
    while True:
        async with session.get(f"https://stablehorde.net/api/v2/interrogate/status/{session_id}") as response:
            response.raise_for_status()

            response = await response.json()
            if response["state"] == "done":
                break

            await asyncio.sleep(random.randint(1, 2))
    return response
