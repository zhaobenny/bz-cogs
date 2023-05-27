from discord import Message
import logging

logger = logging.getLogger("red.bz_cogs.ai_user")


def format_text_content(message: Message):
    content = _mention_to_text(message)
    if message.author.id == message.guild.me.id:
        return f'{content}'
    return f'User "{message.author.display_name}" said: {content}'


def _mention_to_text(message: Message) -> str:
    """
    Converts mentions to text
    """
    content = message.content
    mentions = message.mentions + message.role_mentions + message.channel_mentions

    if not mentions:
        return content

    for mentioned in mentions:
        if mentioned in message.channel_mentions:
            content = content.replace(mentioned.mention, f'#{mentioned.name}')
        else:
            name = mentioned.nick or mentioned.name
            content = content.replace(mentioned.mention, f'@{name}')

    return content


def format_embed_content(message: Message):
    return f'User "{message.author.display_name}" sent: [Embed with title "{message.embeds[0].title}" and description "{message.embeds[0].description}"]'


async def format_sticker_content(message: Message):
    try:
        sticker = await message.stickers[0].fetch()
        description = sticker.description or ""
        description_text = f' and description "{description}"' if description else ""
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker.name}"{description_text}]'
    except:
        sticker_name = message.stickers[0].name
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker_name}"]'


def is_embed_valid(message: Message):
    if not message.embeds[0].title or not message.embeds[0].description:
        logger.debug(f"Skipping unloaded / unsupported embed in {message.guild.name}")
        return False
    return True
