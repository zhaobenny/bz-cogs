import logging
from typing import Optional

from discord import Message, MessageType

from aiuser.utils.utilities import mention_to_text

logger = logging.getLogger("red.bz_cogs.aiuser.context")


def format_text_content(message: Message) -> Optional[str]:
    if message.type == MessageType.new_member:
        return f'User "{message.author.display_name}" has joined the server. Their Discord ID is {message.author.id}'
    if not message.content or message.content == "" or message.content.isspace():
        return None
    content = mention_to_text(message)
    if message.author.id == message.guild.me.id:
        return f"{content}"
    return f'User "{message.author.display_name}" said: {content}'


def format_image_placeholder(message: Message) -> str:
    filenames = ", ".join(
        f'"{attachment.filename}"'
        for attachment in message.attachments
        if (attachment.content_type or "").startswith("image/")
    )
    filenames = filenames or f'"{message.attachments[0].filename}"'
    if message.author.id == message.guild.me.id:
        return f"[Images: {filenames}]"
    return f'User "{message.author.display_name}" sent: [Images: {filenames}]'


async def format_sticker_content(message: Message) -> str:
    try:
        sticker = await message.stickers[0].fetch()
        description = sticker.description or ""
        description_text = f' and description "{description}"' if description else ""
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker.name}"{description_text}]'
    except Exception:
        sticker_name = message.stickers[0].name
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker_name}"]'
