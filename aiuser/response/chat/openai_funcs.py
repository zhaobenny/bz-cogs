import json
import logging
from dataclasses import asdict

from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.utilities import get_available_tools
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.functions.serper import search_google
from aiuser.response.chat.functions.tool_defs import (IS_DAYTIME,
                                                      LOCAL_WEATHER,
                                                      LOCATION_WEATHER,
                                                      SERPER_SEARCH)
from aiuser.response.chat.functions.weather import (get_local_weather,
                                                    get_weather, is_daytime)
from aiuser.response.chat.openai import OpenAI_API_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_Functions_API_Generator(OpenAI_API_Generator):
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        self.bot = cog.bot
        super().__init__(cog, ctx, messages)
        self.tool_handlers = {
            SERPER_SEARCH.function.name: self.handle_serper_search,
            LOCATION_WEATHER.function.name: self.handle_location_weather,
            LOCAL_WEATHER.function.name: self.handle_local_weather,
            IS_DAYTIME.function.name: self.handle_is_daytime,
        }

    async def request_openai(self, model):
        kwargs = await self.get_custom_parameters(model)
        available_tools = await get_available_tools(self.config, self.ctx)

        completion = None
        while completion is None:
            if available_tools != []:
                kwargs["tools"] = [asdict(tool) for tool in available_tools]
            elif "tools" in kwargs:
                del kwargs["tools"]

            response = (
                await self.openai_client.chat.completions.create(
                    model=model, messages=self.msg_list.get_json(), **kwargs
                )
            )
            tool_calls = response.choices[0].message.tool_calls
            completion = response.choices[0].message.content

            if not tool_calls or completion:
                break

            if hasattr(response, "error"):
                raise Exception(f"LLM endpoint error: {response.error}")

            await self.handle_tool_calls(available_tools, tool_calls)

        logger.debug(
            f'Generated the following raw response in {self.ctx.guild.name}: "{completion}"'
        )
        return completion


    async def handle_tool_calls(self, available_tools, tool_calls):
        for tool_call in tool_calls:
            function = tool_call.function
            arguments = json.loads(function.arguments)
            result = None

            logger.info(
                f"Handling tool call in {self.ctx.guild.name}: \"{function.name}\" with arguments: \"{arguments}\"")

            handler = self.tool_handlers.get(function.name)
            if handler:
                result = await handler(arguments, available_tools)

            if not result:
                continue

            await self.msg_list.add_system(result, index=len(self.msg_list) + 1)

    async def handle_serper_search(self, arguments, available_tools):
        self.remove_tool_from_available(SERPER_SEARCH, available_tools)
        return await search_google(arguments["query"], (await self.bot.get_shared_api_tokens("serper")).get("api_key"), self.ctx)

    async def handle_location_weather(self, arguments, available_tools):
        self.remove_tool_from_available(LOCATION_WEATHER, available_tools)
        self.remove_tool_from_available(LOCAL_WEATHER, available_tools)
        days = arguments.get("days", 1)
        return await get_weather(arguments["location"], days=days)

    async def handle_local_weather(self, arguments, available_tools):
        self.remove_tool_from_available(LOCATION_WEATHER, available_tools)
        self.remove_tool_from_available(LOCAL_WEATHER, available_tools)
        days = arguments.get("days", 1)
        return await get_local_weather(self.config, self.ctx, days=days)

    async def handle_is_daytime(self, _, available_tools):
        self.remove_tool_from_available(IS_DAYTIME, available_tools)
        return await is_daytime(self.config, self.ctx)

    def remove_tool_from_available(self, tool, available_tools):
        if tool in available_tools:
            available_tools.remove(tool)
