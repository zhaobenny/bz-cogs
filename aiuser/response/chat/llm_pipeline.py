import json
import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessageToolCall
from openai.types.completion import Completion
from redbot.core import Config, commands

from aiuser.config.models import (
    UNSUPPORTED_LOGIT_BIAS_MODELS,
    VISION_SUPPORTED_MODELS,
)
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import ToolCallSchema
from aiuser.messages_list.messages import MessagesList
from aiuser.types.abc import MixinMeta
from aiuser.utils.utilities import get_enabled_tools

logger = logging.getLogger("red.bz_cogs.aiuser")


class LLMPipeline:
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesList):
        self.ctx: commands.Context = ctx
        self.config: Config = cog.config
        self.bot = cog.bot
        self.msg_list = messages
        self.model = messages.model
        self.can_reply = messages.can_reply
        self.messages = messages.get_json()
        self.openai_client = cog.openai_client
        self.enabled_tools: List[ToolCall] = []
        self.available_tools_schemas: List[ToolCallSchema] = []
        self.completion: Optional[str] = None

    async def get_custom_parameters(self) -> Dict[str, Any]:
        try:
            if self.ctx.guild is not None:
                custom_parameters = await self.config.guild(self.ctx.guild).parameters()
                kwargs = json.loads(custom_parameters) if custom_parameters else {}
                if "logit_bias" not in kwargs:
                    weights = await self.config.guild(self.ctx.guild).weights()
                    kwargs["logit_bias"] = json.loads(weights or "{}")
                if (
                    kwargs.get("logit_bias")
                    and self.model in VISION_SUPPORTED_MODELS
                    or self.model in UNSUPPORTED_LOGIT_BIAS_MODELS
                ):
                    logger.warning(f"logit_bias is not supported for model {self.model}, removing...")
                    del kwargs["logit_bias"]
                return kwargs
            else:
                return {}
        except Exception:
            return {}

    async def setup_tools(self):
        if self.ctx.guild is not None:
            if not (await self.config.guild(self.ctx.guild).function_calling()):
                return
            self.enabled_tools = await get_enabled_tools(self.config, self.ctx)
            self.available_tools_schemas = [tool.schema for tool in self.enabled_tools]
        else:
            self.enabled_tools = []
            self.available_tools_schemas = []

    async def call_client(self, kwargs: Dict[str, Any]) -> Union[str, Tuple[str, List[ChatCompletionMessageToolCall]]]:
        if "gpt-3.5-turbo-instruct" in self.model:
            prompt = "\n".join(message["content"] for message in self.messages)
            response: Completion = await self.openai_client.completions.create(
                model=self.model, prompt=prompt, **kwargs
            )
            return response.choices[0].message.content
        else:
            response: ChatCompletion = await self.openai_client.chat.completions.create(
                model=self.model, messages=self.msg_list.get_json(), **kwargs
            )

            tools_calls: List[ChatCompletionMessageToolCall] = response.choices[0].message.tool_calls or []

            return response.choices[0].message.content, tools_calls

    async def create_completion(self) -> Optional[str]:
        kwargs = await self.get_custom_parameters()
        await self.setup_tools()

        while not self.completion:
            if self.available_tools_schemas:
                kwargs["tools"] = [asdict(schema) for schema in self.available_tools_schemas]

            self.completion, tool_calls = await self.call_client(kwargs)

            if tool_calls and not self.completion:
                await self.handle_tool_calls(tool_calls)
            else:
                break

        logger.debug(f'Generated response in {self.ctx.guild.name if self.ctx.guild else "DM"}: "{self.completion}"')
        return self.completion

    async def handle_tool_calls(self, tool_calls: List[ChatCompletionMessageToolCall]):
        await self.msg_list.add_assistant(index=len(self.msg_list) + 1, tool_calls=tool_calls)
        for tool_call in tool_calls:
            function = tool_call.function
            arguments = json.loads(function.arguments)
            result = await self.run_tool(function.name, arguments)
            if result:
                await self.msg_list.add_tool_result(result, tool_call.id, index=len(self.msg_list) + 1)

    async def run_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        for tool in self.enabled_tools:
            if tool.function_name == tool_name:
                logger.info(
                    f'Handling tool call in {self.ctx.guild.name if self.ctx.guild else "DM"}: "{tool_name}" with arguments: "{arguments}"'
                )
                arguments["request"] = self
                return await tool.run(arguments, self.available_tools_schemas)

        self.available_tools_schemas = []
        logger.warning(f'Could not find tool "{tool_name}" in {self.ctx.guild.name if self.ctx.guild else "DM"}')
        return None

    async def run(self) -> Optional[str]:
        try:
            return await self.create_completion()
        except httpx.ReadTimeout:
            logger.error("Failed request to LLM endpoint. Timed out.")
            await self.ctx.react_quietly("💤", message="`aiuser` request timed out")
        except openai.RateLimitError:
            await self.ctx.react_quietly("💤", message="`aiuser` request ratelimited")
        except Exception:
            logger.exception("Failed API request(s) to LLM endpoint")
            await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
        return None
