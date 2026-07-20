from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

import discord
import httpx
import openai
from openai.types.chat import (
    ChatCompletionMessageParam,
)
from redbot.core import commands

from aiuser.config.defaults import DEFAULT_TOOL_CALL_ROUNDS
from aiuser.config.model_info import get_model_info
from aiuser.context.conversation import Conversation
from aiuser.functions.context import ToolContext
from aiuser.llm.base import ChatStepResult, LLMProvider
from aiuser.llm.openai_compatible.endpoints import is_openrouter_endpoint
from aiuser.llm.registry import get_llm_provider
from aiuser.response.logging import log_chat_request, log_chat_step_result
from aiuser.response.tool_manager import ToolManager

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser")


class LLMPipeline:
    """Drives the request/tool-call loop for one response.

    Owns the provider round-trips and the :class:`ToolContext` that tools see.
    Tool side effects (files, suppression) are read back off the ToolContext
    when the loop finishes.
    """

    def __init__(
        self,
        services: "AIUserServices",
        ctx: commands.Context,
        conversation: Conversation,
    ):
        self.services = services
        self.ctx: commands.Context = ctx

        self.conversation = conversation
        self.model: str = conversation.model

        self.provider: Optional[LLMProvider] = None
        self.tool_context = ToolContext(services=services, ctx=ctx)
        self.tool_manager = ToolManager(self)
        self.completion: Optional[str] = None
        self.tool_call_entries: List = []
        self.session_id: Optional[str] = None
        self.request_id = (
            str(self.ctx.message.id)
            if self.conversation.from_message_context
            else uuid4().hex
        )

    @property
    def files_to_send(self) -> List[discord.File]:
        return self.tool_context.files_to_send

    @property
    def suppress_response(self) -> bool:
        return self.tool_context.suppress_response

    async def run(self) -> Optional[str]:
        base_kwargs = await self._build_base_parameters()
        self.provider = await get_llm_provider(self.services)
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
        tool_call_rounds = (
            await self.services.config.guild(
                self.ctx.guild
            ).function_calling_tool_call_rounds()
            or DEFAULT_TOOL_CALL_ROUNDS
        )
        tools_kwargs = self.tool_manager.get_tools_kwargs()
        exhausted_tool_call_rounds = False

        for round_idx in range(tool_call_rounds):
            kwargs = {**base_kwargs, **tools_kwargs}
            step = await self._create_chat_step(kwargs)
            if step is None:
                return None

            if step.content:
                self.completion = step.content
                break
            if step.tool_calls:
                await self.tool_manager.handle_tool_calls(
                    step.tool_calls, step.assistant_extra_fields
                )
                if self.suppress_response:
                    break
                continue

            logger.warning(
                "No content or tool calls received during round %s for message %s "
                "(finish_reason=%s)",
                round_idx,
                self.ctx.message.id,
                step.finish_reason,
            )
            break
        else:
            exhausted_tool_call_rounds = True

        if exhausted_tool_call_rounds and self.tool_call_entries:
            logger.debug(
                f"Tool call round limit reached for message {self.ctx.message.id}; requesting final response without tools"
            )
            step = await self._create_chat_step(base_kwargs)
            if step and step.content:
                self.completion = step.content

        return self.completion

    async def _create_chat_step(
        self, kwargs: Dict[str, Any]
    ) -> Optional[ChatStepResult]:
        try:
            context: List[ChatCompletionMessageParam] = (
                self.conversation.to_chat_payload()
            )
            log_chat_request(context)
            step = await self.provider.create_chat_step(self.model, context, kwargs)
            log_chat_step_result(
                step.content,
                step.tool_calls,
            )
            return step
        except httpx.ReadTimeout:
            logger.error("Failed request to LLM endpoint. Timed out.")
            await self.ctx.react_quietly("💤", message="`aiuser` request timed out")
        except openai.RateLimitError:
            await self.ctx.react_quietly("💤", message="`aiuser` request ratelimited")
        except httpx.HTTPStatusError:
            logger.exception("Failed HTTP request(s) to LLM endpoint")
            await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
        except Exception:
            logger.exception("Failed request(s) to LLM endpoint")
            await self.ctx.react_quietly("⚠️", message="`aiuser` request failed")
        return None

    async def _build_base_parameters(self) -> Dict[str, Any]:
        """
        Build a base kwargs dict for the OpenAI call, including logit_bias handling.
        """
        params = await self.services.config.guild(self.ctx.guild).parameters()
        kwargs: Dict[str, Any] = json.loads(params) if params else {}

        if "logit_bias" not in kwargs:
            weights = await self.services.config.guild(self.ctx.guild).weights()
            weights_dict = json.loads(weights or "{}")
            if weights_dict:
                kwargs["logit_bias"] = weights_dict

        if (
            kwargs.get("logit_bias", False)
            and not get_model_info(self.model).supports_logit_bias
        ):
            logger.warning(
                f"logit_bias is not supported for model {self.model}, removing..."
            )
            kwargs.pop("logit_bias", None)

        if is_openrouter_endpoint(await self.services.config.custom_openai_endpoint()):
            self.session_id = await self._session_id()
            extra_body = kwargs.setdefault("extra_body", {})
            self.session_id = extra_body.setdefault("session_id", self.session_id)
            trace = extra_body.setdefault("trace", {})
            self.request_id = trace.setdefault("trace_id", self.request_id)
            self.tool_context.llm_session_id = self.session_id
            self.tool_context.llm_trace_id = self.request_id

        return kwargs

    async def _session_id(self) -> str:
        state = self.services.reply_channel_states.get(self.ctx.channel.id)
        if (
            self.conversation.from_message_context
            and state
            and state.llm_session_id
            and state.last_bot_reply_at
        ):
            max_history_gap = await self.services.config.guild(
                self.ctx.guild
            ).messages_backread_seconds()
            elapsed = abs(
                (self.ctx.message.created_at - state.last_bot_reply_at).total_seconds()
            )
            if max_history_gap and elapsed <= max_history_gap:
                return state.llm_session_id

        return self.request_id
