from typing import Literal

from discord import Message
import logging

logger = logging.getLogger("red.bz_cogs.ai_user")

RoleType = Literal['user', 'assistant', 'system']


def format_text_content(message: Message):
    author = message.author.nick or message.author.name
    return f'User "{author}" said: {message.content}'


def format_embed_content(message: Message):
    author = message.author.nick or message.author.name
    return f'User "{author}" sent: [Embed with title "{message.embeds[0].title}" and description "{message.embeds[0].description}"]'

async def format_sticker_content(message: Message):
    author = message.author.nick or message.author.name
    try:
        sticker = await message.stickers[0].fetch()
        description = sticker.description or ""
        description_text = f' and description "{description}"' if description else ""
        return f'User "{author}" sent: [Sticker with name "{sticker.name}"{description_text}]'
    except:
        sticker_name = message.stickers[0].name
        return f'User "{author}" sent: [Sticker with name "{sticker_name}"]'

def is_embed_valid(message: Message):
    if not message.embeds[0].title or not message.embeds[0].description:
        logger.debug(f"Skipping unloaded / unsupported embed in {message.guild.name}")
        return False
    return True
