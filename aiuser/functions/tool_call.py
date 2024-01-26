
from dataclasses import asdict

from redbot.core import Config, commands

from aiuser.functions.types import ToolCallSchema


class ToolCall:
    schema: ToolCallSchema = None
    function_name: str = None

    def __init__(self, config: Config, ctx: commands.Context):
        self.config = config
        self.ctx = ctx
        self.bot = ctx.bot

    def run(self, arguments: dict, available_tools: list):
        self.remove_tool_from_available(available_tools)
        return self._handle(arguments)

    def _handle(arguments: dict):
        raise NotImplementedError

    def remove_tool_from_available(self, available_tools: list):
        if self.schema in available_tools:
            available_tools.remove(self.schema)
