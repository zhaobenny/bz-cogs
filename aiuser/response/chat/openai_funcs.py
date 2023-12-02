import json
import logging

from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.functions.serper import search_google
from aiuser.response.chat.openai import OpenAI_API_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_Functions_API_Generator(OpenAI_API_Generator):
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        self.bot = cog.bot
        super().__init__(cog, ctx, messages)

    async def request_openai(self, model):
        custom_parameters = await self.config.guild(self.ctx.guild).parameters()
        kwargs = {}
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_google",
                    "description": "Searches Google for the query for any unknown information or most current infomation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            }
                        },
                        "required": ["query"],
                    },
                }
            },
        ]

        if custom_parameters is not None:
            custom_parameters = json.loads(custom_parameters)
            kwargs.update(custom_parameters)

        if kwargs.get("logit_bias") is None:
            logit_bias = json.loads(
                await self.config.guild(self.ctx.guild).weights() or "{}"
            )
            kwargs["logit_bias"] = logit_bias

        completion = None
        kwargs["tools"] = tools

        while completion is None:
            response = (
                await self.openai_client.chat.completions.create(
                    model=model, messages=self.msg_list.get_json(), **kwargs
                )
            )
            tool_calls = response.choices[0].message.tool_calls
            completion = response.choices[0].message.content

            if not tool_calls:
                break

            for tool_call in tool_calls:
                function = tool_call.function
                arguments = json.loads(function.arguments)

                if function.name == "search_google":
                    kwargs["tool_choice"] = "none"  # temp, remove for multiple tool calls
                    result = await search_google(arguments["query"], api_key=(await self.bot.get_shared_api_tokens("serper")).get("api_key"), guild=self.ctx.guild)
                    if not result:
                        continue
                    await self.msg_list.add_system(
                        result, index=len(self.msg_list) + 1
                    )

        logger.debug(
            f'Generated the following raw response in {self.ctx.guild.name}: "{completion}"'
        )
        return completion
