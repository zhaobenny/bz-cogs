import json
import logging

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
        kwargs["tools"] = await self.get_available_tools()

        while completion is None:
            if kwargs["tools"] == []:
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

            await self.handle_tool_calls(kwargs, tool_calls)

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

    async def handle_tool_calls(self, kwargs, tool_calls):
        for tool_call in tool_calls:
            function = tool_call.function
            arguments = json.loads(function.arguments)

            logger.info(
                f"Handling tool call in {self.ctx.guild.name}: \"{function.name}\" with arguments: \"{arguments}\"")

            if function.name == "search_google":
                kwargs["tools"].remove(SERPER_SEARCH)
                result = await search_google(arguments["query"], (await self.bot.get_shared_api_tokens("serper")).get("api_key"), self.ctx)
            elif function.name == "get_weather" or function.name == "get_local_weather":
                if LOCATION_WEATHER in kwargs["tools"]:
                    kwargs["tools"].remove(LOCATION_WEATHER)
                if LOCAL_WEATHER in kwargs["tools"]:
                    kwargs["tools"].remove(LOCAL_WEATHER)
                days = arguments.get("days", 1)
                if function.name == "get_weather":
                    result = await get_weather(arguments["location"], days=days)
                else:
                    result = await get_local_weather(self.config, self.ctx, days=days)
            elif function.name == "is_daytime_local":
                kwargs["tools"].remove(IS_DAYTIME)
                result = await is_daytime(self.config, self.ctx)

            if not result:
                continue

            await self.msg_list.add_system(result, index=len(self.msg_list) + 1)
