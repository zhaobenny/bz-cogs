import re

import discord


def create_text_prompt(message: discord.Message, bot : discord.Client):
    # define the regular expression pattern to match URLs
    pattern = re.compile(r"(https?://\S+)")
    is_URL = pattern.search(message.content)

    if (not is_URL and not is_acceptable_message(message)):
        return None

    prompt = None

    if is_URL and len(message.embeds) == 0:
        return  # embeds not loaded yet

    if len(message.embeds) > 0:
        prompt = [
            {"role": "system",
             "content": f"You are in a Discord text channel. Respond to anything, including URLs, unhelpfully and cynically in a short message."},
            {"role": "user",
                "content": f"{message.content}, title is {message.embeds[0].title} and the description is {message.embeds[0].description}"}
        ]
    elif not is_URL:
        prompt = [
            {"role": "system",
             "content": f"You are {bot.user.name}.  Do not include \"{bot.user.name}:\" in the response. You are in a Discord text channel. Respond to anything unhelpfully and cynically in a short message."},
            {"role": "user", "content": message.author.name + ":  " + message.content}
        ]

    return prompt


def is_acceptable_message(message: discord.Message):
    if (len(message.content) < 5):
        print(f"[ai_user] Message too short, skipping: {message.content} in {message.guild.name}")
        return False
    words = message.content.split()
    if len(words) > 300:
        print(f"[ai_user] Message too long, skipping: {message.content} in {message.guild.name}")
        return False
    return True
