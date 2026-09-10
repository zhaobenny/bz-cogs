from __future__ import annotations

from typing import Any

from aiuser.functions.context import ToolContext
from aiuser.functions.types import ToolCallSchema


class ToolCall:
    """Base class for tools the LLM can call.

    Subclasses define a ``schema`` / ``function_name`` and implement
    ``_handle``. Tools are stateless; everything they need comes in via the
    :class:`ToolContext`.
    """

    schema: ToolCallSchema = None
    function_name: str = None
    parallel_safe: bool = False

    async def run(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str | None:
        return await self._handle(tool_context, arguments)

    async def _handle(
        self, tool_context: ToolContext, arguments: dict[str, Any]
    ) -> str | None:
        raise NotImplementedError
