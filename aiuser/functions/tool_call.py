from typing import Any, Dict, Optional

from redbot.core import Config, commands
from redbot.core.bot import Red

from aiuser.functions.context import ToolContext
from aiuser.functions.types import ToolCallSchema


class ToolCall:
    """Base class for tools the LLM can call.

    Subclasses define a ``schema`` / ``function_name`` and implement
    ``_handle``. 
    """

    schema: ToolCallSchema = None
    function_name: str = None

    def __init__(self, config: Config, ctx: commands.Context):
        self.config = config
        self.ctx = ctx
        self.bot: Red = ctx.bot

    async def run(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        return await self._handle(tool_context, arguments)

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        raise NotImplementedError
