from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from openai.types.chat import ChatCompletionMessageToolCall
from redbot.core import Config, commands

from aiuser.functions.context import ToolContext
from aiuser.functions.registry import get_enabled_tools
from aiuser.functions.tool_call import ToolCall

logger = logging.getLogger("red.bz_cogs.aiuser")

if TYPE_CHECKING:
    from aiuser.mcp import MCPManager


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    content: str


@dataclass
class PendingToolCall:
    tool_call: ChatCompletionMessageToolCall
    tool: ToolCall
    arguments: dict[str, Any]


class ToolExecutor:
    """Resolves enabled tools and runs the model's tool calls."""

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        tool_context: ToolContext,
        mcp: MCPManager | None = None,
    ):
        self.config = config
        self.ctx = ctx
        self.tool_context = tool_context
        self.mcp = mcp
        self.enabled_tools: list[ToolCall] = []
        self.enabled_tools_map: dict[str, ToolCall] = {}

    async def setup(self):
        if not (await self.config.guild(self.ctx.guild).function_calling()):
            return
        self.enabled_tools = await get_enabled_tools(self.config, self.ctx)
        if self.mcp:
            self.enabled_tools.extend(await self.mcp.tools_for_guild(self.ctx.guild))
        self.enabled_tools_map = {t.function_name: t for t in self.enabled_tools}

    def get_tools_kwargs(self) -> dict[str, Any]:
        """Return the tools parameter for the OpenAI API call, or empty dict if none."""
        if self.enabled_tools:
            return {"tools": [asdict(t.schema) for t in self.enabled_tools]}
        return {}

    async def run_tool_calls(
        self, tool_calls: list[ChatCompletionMessageToolCall]
    ) -> list[ToolResult]:
        """Run the tool calls and return what each one produced."""
        results: list[ToolResult] = []
        parallel_batch: list[PendingToolCall] = []

        for tool_call in tool_calls:
            pending = self._prepare_tool_call(tool_call)
            if pending is None:
                results.append(
                    ToolResult(
                        tool_call.id,
                        f"Invalid tool call {tool_call.function.name!r}; check the tool name and JSON arguments.",
                    )
                )
                continue

            if not pending.tool.parallel_safe:
                results.extend(await self._run_batch(parallel_batch))
                parallel_batch = []
                results.extend(await self._run_batch([pending]))
                continue

            parallel_batch.append(pending)

        results.extend(await self._run_batch(parallel_batch))
        return results

    def _prepare_tool_call(
        self, tool_call: ChatCompletionMessageToolCall
    ) -> PendingToolCall | None:
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

    async def _run_batch(self, batch: list[PendingToolCall]) -> list[ToolResult]:
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

        tool_results: list[ToolResult] = []
        for pending, result in zip(batch, results):
            if isinstance(result, BaseException):
                logger.error(
                    f'Tool call "{pending.tool.function_name}" failed', exc_info=result
                )
                result = f"Tool {pending.tool.function_name} failed with {result!r}."
            if result is not None:
                tool_results.append(ToolResult(pending.tool_call.id, result))
        return tool_results
