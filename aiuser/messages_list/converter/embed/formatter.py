from discord import Message

from aiuser.types.abc import MixinMeta
from aiuser.config.constants import URL_PATTERN
from aiuser.utils.utilities import contains_youtube_link
from aiuser.functions.scrape.tool_call import ScrapeToolCall
from aiuser.messages_list.converter.embed.youtube import format_youtube_embed


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
    else:
        return f'User "{message.author.display_name}" sent: [Embed with title "{message.embeds[0].title}" and description "{message.embeds[0].description}"]'
