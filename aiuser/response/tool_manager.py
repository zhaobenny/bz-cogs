from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageToolCall
from redbot.core import Config, commands

from aiuser.context.conversation import Conversation
from aiuser.context.entry import MessageEntry
from aiuser.functions.context import ToolContext
from aiuser.functions.registry import get_enabled_tools
from aiuser.functions.tool_call import ToolCall

logger = logging.getLogger("red.bz_cogs.aiuser")


@dataclass
class PendingToolCall:
    tool_call: ChatCompletionMessageToolCall
    tool: ToolCall
    arguments: Dict[str, Any]


class ToolManager:
    """Resolves enabled tools and executes tool calls against the conversation."""

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        conversation: Conversation,
        tool_context: ToolContext,
    ):
        self.config = config
        self.ctx = ctx
        self.conversation = conversation
        self.tool_context = tool_context
        self.enabled_tools: List[ToolCall] = []
        self.enabled_tools_map: Dict[str, ToolCall] = {}

    async def setup(self):
        if not (await self.config.guild(self.ctx.guild).function_calling()):
            return
        self.enabled_tools = await get_enabled_tools(self.config, self.ctx)
        self.enabled_tools_map = {t.function_name: t for t in self.enabled_tools}

    def get_tools_kwargs(self) -> Dict[str, Any]:
        """Return the tools parameter for the OpenAI API call, or empty dict if none."""
        if self.enabled_tools:
            return {"tools": [asdict(t.schema) for t in self.enabled_tools]}
        return {}

    async def handle_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        assistant_extra_fields: Optional[Dict[str, Any]] = None,
    ) -> List[MessageEntry]:
        """Run the tool calls and return the conversation entries they produced."""
        entries: List[MessageEntry] = []
        entries.append(
            await self.conversation.append_assistant(
                tool_calls=tool_calls, assistant_extra_fields=assistant_extra_fields
            )
        )

        parallel_batch: List[PendingToolCall] = []

        for tool_call in tool_calls:
            pending = self._prepare_tool_call(tool_call)
            if pending is None:
                entries.append(
                    await self.conversation.append_tool_result(
                        f"Invalid tool call {tool_call.function.name!r}; check the tool name and JSON arguments.",
                        tool_call.id,
                    )
                )
                continue

            if not pending.tool.parallel_safe:
                entries.extend(await self._run_batch(parallel_batch))
                parallel_batch = []
                entries.extend(await self._run_batch([pending]))
                continue

            parallel_batch.append(pending)

        entries.extend(await self._run_batch(parallel_batch))
        return entries

    def _prepare_tool_call(
        self, tool_call: ChatCompletionMessageToolCall
    ) -> Optional[PendingToolCall]:
        fn = tool_call.function
        try:
            arguments = json.loads(fn.arguments or "{}")
        except json.JSONDecodeError:
            logger.exception(
                f"Could not decode tool call arguments for {fn.name}; arguments: {fn.arguments!r}"
            )
            return None

        tool = self.enabled_tools_map.get(fn.name)
        if not tool:
            logger.warning(f'Could not find tool "{fn.name}"')
            return None

        logger.info(
            f'Handling tool call "{fn.name}" with args keys: {list(arguments.keys())}'
        )
        return PendingToolCall(tool_call, tool, dict(arguments))

    async def _run_batch(self, batch: List[PendingToolCall]) -> List[MessageEntry]:
        if not batch:
            return []

        if len(batch) > 1:
            logger.debug("Handling %s parallel-safe tool calls", len(batch))
        results = await asyncio.gather(
            *(
                pending.tool.run(self.tool_context, pending.arguments)
                for pending in batch
            ),
            return_exceptions=True,
        )

        entries: List[MessageEntry] = []
        for pending, result in zip(batch, results):
            if isinstance(result, BaseException):
                logger.error(
                    f'Tool call "{pending.tool.function_name}" failed', exc_info=result
                )
                result = f"Tool {pending.tool.function_name} failed with {result!r}."
            if result is not None:
                entries.append(
                    await self.conversation.append_tool_result(
                        result, pending.tool_call.id
                    )
                )
        return entries
