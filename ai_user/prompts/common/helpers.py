from typing import Literal

from discord import Message

RoleType = Literal['user', 'assistant', 'system']

def format_text_content(message : Message):
    return f"{message.author.name} said: {message.content}"
