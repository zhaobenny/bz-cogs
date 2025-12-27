from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import discord
import httpx
import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
)
from redbot.core import Config, commands

from aiuser.config.models import (
    UNSUPPORTED_LOGIT_BIAS_MODELS,
    VISION_SUPPORTED_MODELS,
)
from aiuser.context.messages import MessagesThread
from aiuser.response.tool_manager import ToolManager
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")

MAX_TOOL_CALL_ROUNDS = 8


@dataclass
class ChatStepResult:
    content: Optional[str]
    tool_calls: List[ChatCompletionMessageToolCall]


class LLMPipeline:
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesThread):
        self.cog = cog
        self.ctx: commands.Context = ctx
        self.config: Config = cog.config
        self.bot = cog.bot

        self.msg_list: MessagesThread = messages
        self.model: str = messages.model

        self.openai_client = cog.openai_client
        self.tool_manager = ToolManager(self)
        self.completion: Optional[str] = None
        self.files_to_send: List[discord.File] = []

    async def run(self) -> Optional[str]:
        base_kwargs = await self._build_base_parameters()
        await self.tool_manager.setup()

        for round_idx in range(MAX_TOOL_CALL_ROUNDS):
            kwargs = {**base_kwargs, **self.tool_manager.get_tools_kwargs()}

            try:
                step = await self._call_client(kwargs)
            except httpx.ReadTimeout:
                logger.error("Failed request to LLM endpoint. Timed out.")
                await self.ctx.react_quietly("💤", message="`aiuser` request timed out")
                return None
            except openai.RateLimitError:
                await self.ctx.react_quietly(
                    "💤", message="`aiuser` request ratelimited"
                )
                return None
            except Exception:
                logger.exception("Failed API request(s) to LLM endpoint")
                await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
                return None

            if step.content:
                self.completion = step.content
                break
            elif step.tool_calls:
                await self.tool_manager.handle_tool_calls(step.tool_calls)
            else:
                logger.warning(
                    f"No content or tool calls received in {self.ctx.guild.name} during round {round_idx} for {self.ctx.message.id}"
                )
                break

        if self.completion:
            cleaned = self.completion[:200].strip().replace("\n", " ")
            ellipsis = "..." if len(self.completion) > 200 else ""
            logger.debug(
                f'Generated response in {self.ctx.guild.name}: "{cleaned}{ellipsis}"'
            )

        return self.completion

    async def _build_base_parameters(self) -> Dict[str, Any]:
        """
        Build a base kwargs dict for the OpenAI call, including logit_bias handling.
        """
        params = await self.config.guild(self.ctx.guild).parameters()
        kwargs: Dict[str, Any] = json.loads(params) if params else {}

        if "logit_bias" not in kwargs:
            weights = await self.config.guild(self.ctx.guild).weights()
            weights_dict = json.loads(weights or "{}")
            if weights_dict:
                kwargs["logit_bias"] = weights_dict

        unsupported_models = VISION_SUPPORTED_MODELS + UNSUPPORTED_LOGIT_BIAS_MODELS
        is_unsupported_logit_bias = any(m in self.model for m in unsupported_models)
        if kwargs.get("logit_bias", False) and is_unsupported_logit_bias:
            logger.warning(
                f"logit_bias is not supported for model {self.model}, removing..."
            )
            kwargs.pop("logit_bias", None)

        return kwargs

    async def _call_client(self, kwargs: Dict[str, Any]) -> ChatStepResult:
        """
        Call the OpenAI chat endpoint with the current message thread and kwargs.
        """
        context: List[ChatCompletionMessageParam] = self.msg_list.get_json()
        response: ChatCompletion = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=context,
            **kwargs,
        )

        message = response.choices[0].message
        content: Optional[str] = message.content
        tool_calls_raw = message.tool_calls

        tool_calls: List[ChatCompletionMessageToolCall] = (
            list(tool_calls_raw) if tool_calls_raw else []
        )

        return ChatStepResult(content=content, tool_calls=tool_calls)

    def _next_index(self) -> int:
        return len(self.msg_list) + 1
