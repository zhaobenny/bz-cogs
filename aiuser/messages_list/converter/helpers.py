import logging

from discord import Message

from aiuser.common.constants import URL_PATTERN

logger = logging.getLogger("red.bz_cogs.aiuser")



def format_text_content(message: Message):
    if not message.content or message.content == "" or message.content.isspace():
        return None
    content = mention_to_text(message)
    if message.author.id == message.guild.me.id:
        return f'{content}'
    return f'User "{message.author.display_name}" said: {content}'


def format_embed_text_content(message: Message):
    content = mention_to_text(message)
    content = URL_PATTERN.sub("", content)
    if not content or content == "" or content.isspace():
        return None
    if message.author.id == message.guild.me.id:
        return f'{content}'
    return f'User "{message.author.display_name}" said: {content}'

def format_generic_image(message : Message):
    if message.author.id == message.guild.me.id:
        return f'[Image: "{message.attachments[0].filename}"]'
    return f'User "{message.author.display_name}" sent: [Image: "{message.attachments[0].filename}"]'


async def format_sticker_content(message: Message):
    try:
        sticker = await message.stickers[0].fetch()
        description = sticker.description or ""
        description_text = f' and description "{description}"' if description else ""
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker.name}"{description_text}]'
    except:
        sticker_name = message.stickers[0].name
        return f'User "{message.author.display_name}" sent: [Sticker with name "{sticker_name}"]'


def mention_to_text(message: Message) -> str:
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
        elif mentioned in message.role_mentions:
            content = content.replace(mentioned.mention, f'@{mentioned.name}')
        else:
            content = content.replace(mentioned.mention, f'@{mentioned.display_name}')

    return content
