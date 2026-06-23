import asyncio
import functools
import logging
import random
from datetime import datetime
from typing import Callable, Coroutine

import discord
import tiktoken
from discord import Message
from redbot.core import commands

from aiuser.config.constants import (
    FALLBACK_TOKENIZER,
    YOUTUBE_URL_PATTERN,
)

logger = logging.getLogger("red.bz_cogs.aiuser")


def get_tokenizer_encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model), model, False
    except KeyError:
        model_name = str(model or "")
        base_name = model_name.rsplit("/", 1)[-1]
        if base_name.startswith(("gpt-5.", "gpt-4.1.", "gpt-4o.")):
            try:
                return tiktoken.get_encoding("o200k_base"), "o200k_base", True
            except ValueError:
                logger.debug(
                    "tiktoken does not provide o200k_base; falling back to %s",
                    FALLBACK_TOKENIZER,
                )
        return tiktoken.get_encoding(FALLBACK_TOKENIZER), FALLBACK_TOKENIZER, True


def to_thread(timeout=300):
    def decorator(func: Callable) -> Coroutine:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, func, *args, **kwargs), timeout
            )
            return result

        return wrapper

    return decorator


async def format_variables(ctx: commands.Context, text: str):
    """
    Insert supported variables into string if they are present
    """
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    app_info = await ctx.bot.application_info()
    botowner = app_info.owner.name
    authorname = ctx.message.author.display_name
    # Webhook messages have User objects instead of Member objects
    if isinstance(ctx.message.author, discord.Member):
        authortoprole = ctx.message.author.top_role.name
    else:
        authortoprole = "Webhook"  # Default for webhook messages
    authormention = ctx.message.author.mention

    servername = ctx.guild.name
    channelname = ctx.message.channel.name
    currentdate = datetime.today().strftime("%Y/%m/%d")
    currentweekday = datetime.today().strftime("%A")
    currenttime = datetime.today().strftime("%H:%M")

    randomnumber = random.randint(0, 100)

    if isinstance(ctx.message.channel, discord.Thread):
        channeltopic = getattr(ctx.message.channel.parent, "topic", "No topic found")
    else:
        channeltopic = getattr(ctx.message.channel, "topic", "No topic found")

    serveremojis = [str(e) for e in ctx.message.guild.emojis]
    random.shuffle(serveremojis)
    serveremojis = " ".join(serveremojis)

    try:
        res = text.format(
            botname=botname,
            botowner=botowner,
            authorname=authorname,
            authortoprole=authortoprole,
            authormention=authormention,
            servername=servername,
            serveremojis=serveremojis,
            channelname=channelname,
            channeltopic=channeltopic,
            currentdate=currentdate,
            currentweekday=currentweekday,
            currenttime=currenttime,
            randomnumber=randomnumber,
        )
        return res
    except KeyError:
        logger.exception("Invalid key in message", exc_info=True)
        return text


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
            content = content.replace(mentioned.mention, f"#{mentioned.name}")
        elif mentioned in message.role_mentions:
            content = content.replace(mentioned.mention, f"@{mentioned.name}")
        else:
            content = content.replace(mentioned.mention, f"@{mentioned.display_name}")

    return content


def is_embed_valid(message: Message):
    if (
        (len(message.embeds) == 0)
        or (not message.embeds[0].title)
        or (not message.embeds[0].description)
    ):
        return False
    return True


async def wait_for_embed(ctx: commands.Context) -> commands.Context:
    start_time = asyncio.get_event_loop().time()
    while not is_embed_valid(ctx.message):
        ctx.message = await ctx.channel.fetch_message(ctx.message.id)
        if asyncio.get_event_loop().time() - start_time >= 3:
            break
        await asyncio.sleep(1)
    return ctx


def contains_youtube_link(content):
    match = YOUTUBE_URL_PATTERN.search(content)
    return bool(match)


async def encode_text_to_tokens(text: str, model: str = FALLBACK_TOKENIZER) -> int:
    encoding, _, _ = get_tokenizer_encoding(model)
    return await asyncio.to_thread(
        lambda: len(encoding.encode(text, disallowed_special=()))
    )
