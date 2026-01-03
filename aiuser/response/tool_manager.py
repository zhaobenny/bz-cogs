from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Dict, List

from openai.types.chat import ChatCompletionMessageToolCall

from aiuser.functions.tool_call import ToolCall

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline
from aiuser.utils.utilities import get_enabled_tools

logger = logging.getLogger("red.bz_cogs.aiuser")


class ToolManager:
    def __init__(self, pipeline: "LLMPipeline"):
        self.pipeline = pipeline
        self.enabled_tools: List[ToolCall] = []
        self.enabled_tools_map: Dict[str, ToolCall] = {}

    async def setup(self) -> None:
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
        self, tool_calls: List[ChatCompletionMessageToolCall]
    ) -> None:
        entry = await self.pipeline.msg_list.add_assistant(
            index=self.pipeline._next_index(), tool_calls=tool_calls
        )
        if entry:
            self.pipeline.tool_call_entries.append(entry)

        for tool_call in tool_calls:
            fn = tool_call.function
            try:
                arguments = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                logger.exception(
                    f"Could not decode tool call arguments for {fn.name}; arguments: {fn.arguments!r}"
                )
                continue

            tool = self.enabled_tools_map.get(fn.name)
            if tool:
                logger.info(
                    f'Handling tool call in {self.pipeline.ctx.guild.name}: "{fn.name}" with args keys: {list(arguments.keys())}'
                )
                result = await tool.run(self.pipeline, dict(arguments))
                if result is not None:
                    entry = await self.pipeline.msg_list.add_tool_result(
                        result, tool_call.id, index=self.pipeline._next_index()
                    )
                    if entry:
                        self.pipeline.tool_call_entries.append(entry)
            else:
                logger.warning(
                    f'Could not find tool "{fn.name}" in {self.pipeline.ctx.guild.name}'
                )
