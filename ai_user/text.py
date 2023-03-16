import re

import discord

from ai_user.constants import DEFAULT_TEXT_PROMPT


def create_text_prompt(message: discord.Message, bot: discord.Client, default_prompt: str = None):

    if not default_prompt:
        default_prompt = DEFAULT_TEXT_PROMPT

    # define the regular expression pattern to match URLs
    url_pattern = re.compile(r"(https?://\S+)")
    is_URL = url_pattern.search(message.content)

    tenor_pattern = r"^https:\/\/tenor\.com\/view\/"

    if (not is_URL and not is_acceptable_message(message)):
        return None

    prompt = None

    if is_URL and len(message.embeds) == 0:
        return  # embeds not loaded yet

    is_tenor = False
    if (message.embeds):
        is_tenor = re.match(tenor_pattern, message.embeds[0].url)

    if len(message.embeds) > 0 and not is_tenor and message.embeds[0].title and message.embeds[0].description:
        prompt = [
            {"role": "system",
             "content": f"You are in a Discord text channel. {default_prompt}"},
            {"role": "user",
                "content": f"{message.content}, title is {message.embeds[0].title} and the description is {message.embeds[0].description}"}
        ]
    elif not is_URL or is_tenor:
        prompt = [
            {"role": "system",
             "content": f"You are {bot.user.name}.  Do not include \"{bot.user.name}:\" in the response. You are in a Discord text channel. {default_prompt}"},
            {"role": "user", "content": f"\"{message.author.name}\": {message.content}"}
        ]

    return prompt


def is_acceptable_message(message: discord.Message):

    if not message.content:
        return False

    if (len(message.content) < 5):
        print(
            f"[ai_user] Message too short, skipping: {message.content} in {message.guild.name}")
        return False
    words = message.content.split()
    if len(words) > 300:
        print(
            f"[ai_user] Message too long, skipping: {message.content} in {message.guild.name}")
        return False
    return True
