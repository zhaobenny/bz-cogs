import random

import discord


def create_text_prompt(message: discord.Message):
    if (not is_acceptable_message(message)):
        return None

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
