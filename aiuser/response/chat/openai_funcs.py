import json
import logging
from dataclasses import asdict

from redbot.core import commands

from aiuser.abc import MixinMeta
from aiuser.common.utilities import get_enabled_tools
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import ToolCallSchema
from aiuser.messages_list.messages import MessagesList
from aiuser.response.chat.openai import OpenAI_API_Generator

logger = logging.getLogger("red.bz_cogs.aiuser")


class OpenAI_Functions_API_Generator(OpenAI_API_Generator):
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        self.bot = cog.bot
        self.enabled_tools: list[ToolCall] = []
        self.available_tools_schemas: list[ToolCallSchema] = []
        self.completion = None
        super().__init__(cog, ctx, messages)

    async def request_openai(self):
        kwargs = await self.get_custom_parameters()
        self.enabled_tools = await get_enabled_tools(self.config, self.ctx)
        self.available_tools_schemas = [tool.schema for tool in self.enabled_tools]

        while not self.completion:
            if self.available_tools_schemas:
                kwargs["tools"] = [asdict(schema) for schema in self.available_tools_schemas]

            elif "tools" in kwargs:
                del kwargs["tools"]

            response = (
                await self.openai_client.chat.completions.create(
                    model=self.model, messages=self.msg_list.get_json(), **kwargs
                )
            )

            tool_calls = response.choices[0].message.tool_calls
            self.completion = response.choices[0].message.content

            if not tool_calls or self.completion:
                break

            if hasattr(response, "error"):
                raise Exception(f"LLM endpoint error: {response.error}")

            await self.handle_tool_calls(tool_calls)

        logger.debug(
            f'Generated the following raw response in {self.ctx.guild.name}: "{self.completion}"'
        )
        return self.completion

    async def handle_tool_calls(self, tool_calls: list):
        for tool_call in tool_calls:
            function = tool_call.function
            arguments = json.loads(function.arguments)

            result = await self.run_tool(function.name, arguments)

            if not result:
                continue

            await self.msg_list.add_system(result, index=len(self.msg_list) + 1)

    async def run_tool(self, tool_name: str, arguments: dict):
        for tool in self.enabled_tools:  # TODO: map this instead of looping
            if tool.function_name != tool_name:
                continue
            logger.info(f"Handling tool call in {self.ctx.guild.name}: \"{tool_name}\" with arguments: \"{arguments}\"")
            arguments["request"] = self
            return await tool.run(arguments, self.available_tools_schemas)

        self.available_tools_schemas = []
        logger.warning(f"Could not find tool \"{tool_name}\" in {self.ctx.guild.name}")
        return None
