from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageToolCall

from aiuser.functions.registry import get_enabled_tools
from aiuser.functions.tool_call import ToolCall

if TYPE_CHECKING:
    from aiuser.response.pipeline import LLMPipeline

logger = logging.getLogger("red.bz_cogs.aiuser")


@dataclass
class PendingToolCall:
    tool_call: ChatCompletionMessageToolCall
    tool: ToolCall
    arguments: Dict[str, Any]


class ToolManager:
    def __init__(self, pipeline: "LLMPipeline"):
        self.pipeline = pipeline
        self.enabled_tools: List[ToolCall] = []
        self.enabled_tools_map: Dict[str, ToolCall] = {}

    async def setup(self):
        cfg = self.pipeline.config.guild(self.pipeline.ctx.guild)
        if not (await cfg.function_calling()):
            return
        self.enabled_tools = await get_enabled_tools(
            self.pipeline.config, self.pipeline.ctx
        )
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
    ):
        conversation = self.pipeline.conversation
        entry = await conversation.append_assistant(
            tool_calls=tool_calls, assistant_extra_fields=assistant_extra_fields
        )
        self.pipeline.tool_call_entries.append(entry)

        parallel_batch: List[PendingToolCall] = []

        for tool_call in tool_calls:
            pending = self._prepare_tool_call(tool_call)
            if pending is None:
                continue

            if not pending.tool.parallel_safe:
                await self._run_batch(parallel_batch)
                parallel_batch = []
                await self._run_batch([pending])
                continue

            parallel_batch.append(pending)

        await self._run_batch(parallel_batch)

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

    async def _run_batch(self, batch: List[PendingToolCall]) -> None:
        if not batch:
            return

        if len(batch) > 1:
            logger.debug("Handling %s parallel-safe tool calls", len(batch))
            results = await asyncio.gather(
                *(
                    pending.tool.run(self.pipeline.tool_context, pending.arguments)
                    for pending in batch
                )
            )
        else:
            pending = batch[0]
            results = [
                await pending.tool.run(self.pipeline.tool_context, pending.arguments)
            ]

        for pending, result in zip(batch, results):
            if result is not None:
                entry = await self.pipeline.conversation.append_tool_result(
                    result, pending.tool_call.id
                )
                self.pipeline.tool_call_entries.append(entry)
