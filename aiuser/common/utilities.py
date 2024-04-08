import asyncio
import functools
import logging
import random
from datetime import datetime
from typing import Callable, Coroutine

from discord import Message
from openai import AsyncOpenAI
from redbot.core import Config, commands

from aiuser.common.constants import OPENROUTER_URL, YOUTUBE_URL_PATTERN
from aiuser.functions.tool_call import ToolCall

logger = logging.getLogger("red.bz_cogs.aiuser")


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


def format_variables(ctx: commands.Context, text: str):
    """
    Insert supported variables into string if they are present
    """
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    authorname = ctx.message.author.display_name
    authortoprole = ctx.message.author.top_role.name

    servername = ctx.guild.name
    channelname = ctx.message.channel.name
    currentdate = datetime.today().strftime("%Y/%m/%d")
    currentweekday = datetime.today().strftime("%A")
    currenttime = datetime.today().strftime("%H:%M")

    serveremojis = [str(e) for e in ctx.message.guild.emojis]
    random.shuffle(serveremojis)
    serveremojis = ' '.join(serveremojis)

    try:
        res = text.format(
            botname=botname,
            authorname=authorname,
            authortoprole=authortoprole,
            servername=servername,
            serveremojis=serveremojis,
            channelname=channelname,
            currentdate=currentdate,
            currentweekday=currentweekday,
            currenttime=currenttime,
        )
        return res
    except KeyError:
        logger.exception("Invalid key in message", exc_info=True)
        return text


def is_embed_valid(message: Message):
    if (
        (len(message.embeds) == 0)
        or (not message.embeds[0].title)
        or (not message.embeds[0].description)
    ):
        return False
    return True


def contains_youtube_link(content):
    match = YOUTUBE_URL_PATTERN.search(content)
    return bool(match)


def is_using_openai_endpoint(client: AsyncOpenAI):
    return str(client.base_url).startswith("https://api.openai.com/")


def is_using_openrouter_endpoint(client: AsyncOpenAI):
    return str(client.base_url).startswith(OPENROUTER_URL)


async def get_enabled_tools(config: Config, ctx: commands.Context) -> list:
    from aiuser.functions.noresponse.tool_call import NoResponseToolCall
    from aiuser.functions.search.tool_call import SearchToolCall
    from aiuser.functions.weather.tool_call import (IsDaytimeToolCall,
                                                    LocalWeatherToolCall,
                                                    LocationWeatherToolCall)
    tools = []
    if await config.guild(ctx.guild).function_calling_search():
        tools.append(SearchToolCall(config=config, ctx=ctx))
    if await config.guild(ctx.guild).function_calling_weather():
        tools.append(LocationWeatherToolCall(config=config, ctx=ctx))
        tools.append(LocalWeatherToolCall(config=config, ctx=ctx))
        tools.append(IsDaytimeToolCall(config=config, ctx=ctx))
    if await config.guild(ctx.guild).function_calling_no_response():
        tools.append(NoResponseToolCall(config=config, ctx=ctx))
    return tools
