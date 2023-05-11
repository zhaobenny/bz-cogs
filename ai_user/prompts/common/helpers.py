from typing import Literal

from discord import Message
import logging

logger = logging.getLogger("red.bz_cogs.ai_user")

RoleType = Literal['user', 'assistant', 'system']


def format_text_content(message: Message):
    return f"{message.author.name} said: {message.content}"


def format_embed_content(message: Message):
    return f"{message.author.name}: [Embed with title \"{message.embeds[0].title}\" and description \"{message.embeds[0].description}\"]"


def is_embed_valid(message: Message):
    if not message.embeds[0].title or not message.embeds[0].description:
        logger.debug(f"Skipping unloaded / unsupported embed in {message.guild.name}")
        return False
    return True
