from typing import TYPE_CHECKING, Any, Dict

from redbot.core import Config, commands
from redbot.core.bot import Red

from aiuser.functions.types import ToolCallSchema

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline


class ToolCall:
    schema: ToolCallSchema = None
    function_name: str = None

    def __init__(self, config: Config, ctx: commands.Context):
        self.config = config
        self.ctx = ctx
        self.bot: Red = ctx.bot

    async def run(
        self,
        request: "LLMPipeline",
        arguments: Dict[str, Any],
    ):
        return await self._handle(request, arguments)

    async def _handle(self, request: "LLMPipeline", arguments: Dict[str, Any]):
        raise NotImplementedError
