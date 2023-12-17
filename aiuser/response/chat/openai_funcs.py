import json
import logging
from dataclasses import asdict

from redbot.core import commands

from aiuser.abc import MixinMeta
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

    async def request_openai(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(
                await self.config.guild(self.ctx.guild).weights() or "{}"
            )
            kwargs["logit_bias"] = logit_bias

        completion = None
        available_tools = await self.get_available_tools()

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

            await self.handle_tool_calls(available_tools, tool_calls)

        logger.debug(
            f'Generated the following raw response in {self.ctx.guild.name}: "{completion}"'
        )
        return completion

    async def get_available_tools(self):
        tools = []
        if await self.config.guild(self.ctx.guild).function_calling_search():
            tools.append(SERPER_SEARCH)
        if await self.config.guild(self.ctx.guild).function_calling_weather():
            tools.append(LOCAL_WEATHER)
            tools.append(LOCATION_WEATHER)
            tools.append(IS_DAYTIME)
        return tools

    async def handle_tool_calls(self, available_tools, tool_calls):
        for tool_call in tool_calls:
            function = tool_call.function
            arguments = json.loads(function.arguments)
            result = None

            logger.info(
                f"Handling tool call in {self.ctx.guild.name}: \"{function.name}\" with arguments: \"{arguments}\"")

            if function.name == SERPER_SEARCH.function.name:
                available_tools.remove(SERPER_SEARCH)
                result = await search_google(arguments["query"], (await self.bot.get_shared_api_tokens("serper")).get("api_key"), self.ctx)
            elif function.name == LOCATION_WEATHER.function.name or function.name == LOCAL_WEATHER.function.name:
                if LOCATION_WEATHER in available_tools:
                    available_tools.remove(LOCATION_WEATHER)
                if LOCAL_WEATHER in available_tools:
                    available_tools.remove(LOCAL_WEATHER)
                days = arguments.get("days", 1)
                if function.name == LOCATION_WEATHER.function.name:
                    result = await get_weather(arguments["location"], days=days)
                else:
                    result = await get_local_weather(self.config, self.ctx, days=days)
            elif function.name == IS_DAYTIME.function.name:
                available_tools.remove(IS_DAYTIME)
                result = await is_daytime(self.config, self.ctx)

            if not result:
                continue

            await self.msg_list.add_system(result, index=len(self.msg_list) + 1)
