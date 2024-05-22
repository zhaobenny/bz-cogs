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


async def format_variables(ctx: commands.Context, text: str):
    """
    Insert supported variables into string if they are present
    """
    botname = ctx.message.guild.me.nick or ctx.bot.user.display_name
    app_info = await ctx.bot.application_info()
    botowner = app_info.owner.name
    authorname = ctx.message.author.display_name
    authortoprole = ctx.message.author.top_role.name
    authormention = ctx.message.author.mention

    servername = ctx.guild.name
    channelname = ctx.message.channel.name
    channeltopic = ctx.message.channel.topic
    currentdate = datetime.today().strftime("%Y/%m/%d")
    currentweekday = datetime.today().strftime("%A")
    currenttime = datetime.today().strftime("%H:%M")

    serveremojis = [str(e) for e in ctx.message.guild.emojis]
    random.shuffle(serveremojis)
    serveremojis = ' '.join(serveremojis)

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
    from aiuser.functions.scrape.tool_call import ScrapeToolCall
    from aiuser.functions.search.tool_call import SearchToolCall
    from aiuser.functions.weather.tool_call import (IsDaytimeToolCall,
                                                    LocalWeatherToolCall,
                                                    LocationWeatherToolCall)

    tool_classes = {
        SearchToolCall.function_name: SearchToolCall,
        LocationWeatherToolCall.function_name: LocationWeatherToolCall,
        LocalWeatherToolCall.function_name: LocalWeatherToolCall,
        IsDaytimeToolCall.function_name: IsDaytimeToolCall,
        NoResponseToolCall.function_name: NoResponseToolCall,
        ScrapeToolCall.function_name: ScrapeToolCall,
    }

    enabled_tool_names: list = await config.guild(ctx.guild).function_calling_functions()

    tools = []

    for tool_name in enabled_tool_names:
        tool_class = tool_classes.get(tool_name)
        if tool_class:
            tools.append(tool_class(config=config, ctx=ctx))

    return tools
