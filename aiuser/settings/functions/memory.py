from redbot.core import commands
from aiuser.settings.functions.utilities import FunctionsGroupMixin, functions


class MemoryFunctionSettings(FunctionsGroupMixin):
    @functions.command(name="memory")
    async def toggle_memory_function(self, ctx: commands.Context):
        """Enable/disable the LLM's ability to save important facts about user/context to memory."""
        from aiuser.functions.memory.tool_call import SaveMemoryToolCall

        tool_names = [SaveMemoryToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Memory")
