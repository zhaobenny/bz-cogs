import random
import re
import time
import json


import discord


def create_text_prompt(message: discord.Message):
    # define the regular expression pattern to match URLs
    pattern = re.compile(r"(https?://\S+)")
    is_URL = pattern.search(message.content)


    if (not is_URL and not is_acceptable_message(message)):
        return None

    prompt = None

    if is_URL and len(message.embeds) == 0:
        return # embeds not loaded yet


    if len(message.embeds) > 0:
        prompt = [
            {"role": "system",
            "content": f"You are in a Discord text channel. Respond to anything, including URLs, unhelpfully and cynically in a short message."},
            {"role": "user", "content": f"{message.content}, title is {message.embeds[0].title} and the description is {message.embeds[0].description}"}
        ]
    elif not is_URL:
        prompt = [
            {"role": "system",
            "content": "You are in a Discord text channel. Respond to anything, including URLs, unhelpfully and cynically in a short message."},
            {"role": "user", "content": message.author.name + ":  " + message.content}
        ]

    return prompt

def is_acceptable_message(message: discord.Message):
    if (len(message.content) < 5):
        return False
    words = message.content.split()
    if len(words) > 300:
        return False
    if (len(words) == 1 and (random.random() > 0.5)):
        return False
    return True
