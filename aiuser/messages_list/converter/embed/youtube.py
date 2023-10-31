
import logging
import re

import aiohttp
from discord import Message
from redbot.core.bot import Red
from tenacity import retry, stop_after_attempt, wait_random

logger = logging.getLogger("red.bz_cogs.aiuser")


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
    pattern = r"(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|v\/|t\/\S*?\/?)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)

    if match:
        video_id = match.group(1)
        return video_id
    else:
        return None


@retry(
    wait=wait_random(min=1, max=2), stop=(stop_after_attempt(4)),
    reraise=True
)
async def get_video_details(api_key, video_id):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={api_key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                video_data = await response.json()
                snippet = video_data["items"][0]["snippet"]
                video_title = snippet["title"]
                channel_title = snippet["channelTitle"]
                description = snippet["description"]
                return (video_title, channel_title, description)
            else:
                response.raise_for_status()
