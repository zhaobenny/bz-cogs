
import logging
import re

import aiohttp
from discord import Message
from redbot.core.bot import Red
from tenacity import retry, stop_after_attempt, wait_random

logger = logging.getLogger("red.bz_cogs.aiuser")

YOUTUBE_URL_PATTERN = r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos?part=snippet&id={}&key={}"


async def format_youtube_embed(bot: Red, message: Message):
    api_key = (await bot.get_shared_api_tokens("youtube")).get("api_key")
    video_id = await get_video_id(message.content)
    author = message.author.display_name

    if not video_id:
        return None

    try:
        video_title, channel_title, description = await get_video_details(api_key, video_id)
    except:
        logger.error(f"Failed request to Youtube API", exc_info=True)
        return None

    return (f'User "{author}" sent: [Link to Youtube video with title "{video_title}" and description "{description}" from channel "{channel_title}"]')


async def get_video_id(url):
    match = re.search(YOUTUBE_URL_PATTERN, url)

    if match:
        return match.group(1)
    else:
        return None


@retry(
    wait=wait_random(min=1, max=2), stop=(stop_after_attempt(3)),
    reraise=True
)
async def get_video_details(api_key, video_id):
    url = YOUTUBE_API_URL.format(video_id, api_key)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            video_data = await response.json()
            snippet = video_data["items"][0]["snippet"]
            video_title = snippet["title"]
            channel_title = snippet["channelTitle"]
            description = snippet["description"]
            return (video_title, channel_title, description)
