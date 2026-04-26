from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import discord
import httpx
import openai
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from redbot.core import Config, commands

from aiuser.config.models import (
    UNSUPPORTED_LOGIT_BIAS_MODELS,
    VISION_SUPPORTED_MODELS,
)
from aiuser.context.messages import MessagesThread
from aiuser.llm.base import LLMProvider
from aiuser.llm.registry import get_llm_provider
from aiuser.response.logging import log_chat_request, log_chat_step_result
from aiuser.response.tool_manager import ToolManager
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")

MAX_TOOL_CALL_ROUNDS = 8


class LLMPipeline:
    def __init__(self, cog: MixinMeta, ctx: commands.Context, messages: MessagesThread):
        self.cog = cog
        self.ctx: commands.Context = ctx
        self.config: Config = cog.config
        self.bot = cog.bot

        self.msg_list: MessagesThread = messages
        self.model: str = messages.model

        self.provider: Optional[LLMProvider] = None
        self.tool_manager = ToolManager(self)
        self.completion: Optional[str] = None
        self.files_to_send: List[discord.File] = []
        self.tool_call_entries: List = []

    async def run(self) -> Optional[str]:
        base_kwargs = await self._build_base_parameters()
        self.provider = await get_llm_provider(self.cog)
        if self.provider is None:
            logger.error("No LLM backend available while starting response pipeline")
            if self.ctx.interaction:
                await self.ctx.send(
                    ":warning: No LLM backend available.", ephemeral=True
                )
            else:
                await self.ctx.react_quietly(
                    "⚠️", message="`aiuser` has no LLM backend available"
                )
            return None
        await self.tool_manager.setup()

        for round_idx in range(MAX_TOOL_CALL_ROUNDS):
            kwargs = {**base_kwargs, **self.tool_manager.get_tools_kwargs()}

            try:
                context: List[ChatCompletionMessageParam] = self.msg_list.get_json()
                log_chat_request(context)
                step = await self.provider.create_chat_step(self.model, context, kwargs)
                log_chat_step_result(
                    step.content,
                    step.tool_calls,
                )
            except httpx.ReadTimeout:
                logger.error("Failed request to LLM endpoint. Timed out.")
                await self.ctx.react_quietly("💤", message="`aiuser` request timed out")
                return None
            except openai.RateLimitError:
                await self.ctx.react_quietly(
                    "💤", message="`aiuser` request ratelimited"
                )
                return None
            except httpx.HTTPStatusError:
                logger.exception("Failed HTTP request(s) to LLM endpoint")
                await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
                return None
            except Exception:
                logger.exception("Failed request(s) to LLM endpoint")
                await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
                return None

            if step.content:
                self.completion = step.content
                break
            elif step.tool_calls:
                await self.tool_manager.handle_tool_calls(step.tool_calls)
            else:
                logger.warning(
                    f"No content or tool calls received during round {round_idx} for message {self.ctx.message.id}"
                )
                break

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

        extra_body = kwargs.setdefault("extra_body", {})
        extra_body.setdefault(
            "session_id",
            f"{self.ctx.message.id}",
        )

        return kwargs

    def _next_index(self) -> int:
        return len(self.msg_list) + 1
