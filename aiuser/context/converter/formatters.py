import logging

from discord import Message, MessageType

from aiuser.utils.utilities import mention_to_text

logger = logging.getLogger("red.bz_cogs.aiuser.context")


def format_text_content(message: Message):
    if message.type == MessageType.new_member:
        return f'User "{message.author.display_name}" has joined the server. Their Discord ID is {message.author.id}'
    if not message.content or message.content == "" or message.content.isspace():
        return None
    content = mention_to_text(message)
    if message.author.id == message.guild.me.id:
        return f"{content}"
    return f'User "{message.author.display_name}" said: {content}'


def format_image_placeholder(message: Message):
    if message.author.id == message.guild.me.id:
        return f'[Image: "{message.attachments[0].filename}"]'
    return f'User "{message.author.display_name}" sent: [Image: "{message.attachments[0].filename}"]'


async def format_sticker_content(message: Message):
    try:
        sticker = await message.stickers[0].fetch()
        description = sticker.description or ""
        description_text = f' and description "{description}"' if description else ""
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker.name}"{description_text}]'
    except Exception:
        sticker_name = message.stickers[0].name
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker_name}"]'
