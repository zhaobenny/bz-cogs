from redbot.core import commands
from aiuser.settings.functions.utilities import FunctionsGroupMixin, functions

class AutolearnFunctionSettings(FunctionsGroupMixin):
    @functions.command(name="autolearn")
    async def toggle_autolearn_function(self, ctx: commands.Context):
        """Enable/disable the LLM's ability to automatically save important facts about the user/context to memory."""
        from aiuser.functions.autolearn.tool_call import AutolearnToolCall
        
        tool_names = [AutolearnToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Autolearn")
