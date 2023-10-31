
from discord import Message

from aiuser.abc import MixinMeta
from aiuser.common.utilities import contains_youtube_link
from aiuser.messages_list.converter.embed.youtube import \
    format_youtube_embed


async def format_embed_content(cog: MixinMeta, message: Message):
    bot = cog.bot
    if (contains_youtube_link(message.content) and (await bot.get_shared_api_tokens("youtube")).get("api_key")):
        return await format_youtube_embed(bot, message)
    else:
        return f'User "{message.author.display_name}" sent: [Embed with title "{message.embeds[0].title}" and description "{message.embeds[0].description}"]'
