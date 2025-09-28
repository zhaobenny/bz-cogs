from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

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
        self.ctx: commands.Context = ctx
        self.config: Config = cog.config
        self.bot = cog.bot

        self.msg_list: MessagesThread = messages
        self.model: str = messages.model

        self.openai_client = cog.openai_client
        self.tool_manager = ToolManager(self)
        self.completion: Optional[str] = None

    async def run(self) -> Optional[str]:
        try:
            return await self._create_completion()
        except httpx.ReadTimeout:
            logger.error("Failed request to LLM endpoint. Timed out.")
            await self.ctx.react_quietly("💤", message="`aiuser` request timed out")
        except openai.RateLimitError:
            await self.ctx.react_quietly("💤", message="`aiuser` request ratelimited")
        except Exception:
            logger.exception("Failed API request(s) to LLM endpoint")
            await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
        return None

    async def _create_completion(self) -> Optional[str]:
        base_kwargs = await self._build_base_parameters()
        await self.tool_manager.setup()

        for round_idx in range(MAX_TOOL_CALL_ROUNDS):
            kwargs = dict(base_kwargs)
            if self.tool_manager.available_tools_schemas:
                kwargs["tools"] = [asdict(s) for s in self.tool_manager.available_tools_schemas]

            step = await self._call_client(kwargs)

            if step.content:
                self.completion = step.content
                break

            if step.tool_calls:
                await self.tool_manager.handle_tool_calls(step.tool_calls)
                continue

            logger.debug(
                f"Max round reached {round_idx} for response in {self.ctx.guild.name}."
            )
            break

        if self.completion:
            preview = self.completion.strip().replace("\n", " ")
            logger.debug(
                f'Generated response in {self.ctx.guild.name}: "{preview[:200]}{"..." if len(preview) > 200 else ""}"'
            )
        else:
            logger.debug(f"No completion generated in {self.ctx.guild.name}")

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

        if kwargs.get("logit_bias", False) and (
            self.model in VISION_SUPPORTED_MODELS or self.model in UNSUPPORTED_LOGIT_BIAS_MODELS
        ):
            logger.warning(f"logit_bias is not supported for model {self.model}, removing...")
            kwargs.pop("logit_bias", None)

        return kwargs

    async def _call_client(self, kwargs: Dict[str, Any]) -> ChatStepResult:
        """
        Call the OpenAI chat endpoint with the current message thread and kwargs.
        """
        context : List[ChatCompletionMessageParam] = self.msg_list.get_json()
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