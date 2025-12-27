import copy
import json
import logging

import aiohttp
from discord import Message
from tenacity import retry, stop_after_attempt, wait_random

from aiuser.config.constants import URL_PATTERN, YOUTUBE_VIDEO_ID_PATTERN
from aiuser.context.converter.formatters import format_text_content
from aiuser.functions.scrape.tool_call import ScrapeToolCall
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser")

YOUTUBE_API_URL = (
    "https://www.googleapis.com/youtube/v3/videos?part=snippet&id={}&key={}"
)


async def format_embed_content(cog: MixinMeta, message: Message):
    yt_api_key = (await cog.bot.get_shared_api_tokens("youtube")).get("api_key")
    if yt_api_key and contains_youtube_link(message.content):
        return await format_youtube_embed(yt_api_key, message)
    elif (
        URL_PATTERN.search(message.content)
        and ScrapeToolCall.function_name
        in await cog.config.guild(message.guild).function_calling_functions()
    ):
        return None
    try:
        return f'User "{message.author.display_name}" sent: [Embed with title "{message.embeds[0].title}" and description "{message.embeds[0].description}"]'
    except Exception:
        logger.debug(
            "Failed to format embed content! \n Embeds in the message was: %s",
            json.dumps(message.embeds, indent=4),
        )
        return None


def format_embed_message_content(message: Message):
    message_copy = copy.copy(message)
    message_copy.content = URL_PATTERN.sub("", message_copy.content)
    return format_text_content(message_copy)


async def format_youtube_embed(api_key: str, message: Message):
    video_id = await get_video_id(message.content)
    author = message.author.display_name

    if not video_id:
        return None

    try:
        video_title, channel_title, description = await get_video_details(
            api_key, video_id
        )
    except Exception:
        logger.error("Failed request to Youtube API", exc_info=True)
        return None

    return f'User "{author}" sent: [Link to Youtube video with title "{video_title}" and description "{description}" from channel "{channel_title}"]'


async def get_video_id(url):
    match = YOUTUBE_VIDEO_ID_PATTERN.search(url)

    if match:
        return match.group(1)
    else:
        return None


@retry(wait=wait_random(min=1, max=2), stop=(stop_after_attempt(3)), reraise=True)
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
