import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class MemoryFunctionSettings(FunctionToggleHelperMixin):
    @functions.command(name="memory")
    async def toggle_memory_function(self, ctx: commands.Context):
        """Enable/disable the LLM's ability to save important facts about user/context to memory."""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions()
        enabling = names.SAVE_MEMORY not in enabled_tools
        querying_disabled = enabling and not await guild_conf.query_memories()

        await self.toggle_function_group(
            ctx, [names.SAVE_MEMORY, names.READ_MEMORY], "Memory"
        )

        if querying_disabled:
            embed = discord.Embed(
                title=":warning: Saved memory querying is still off",
                description=(
                    f"Enable it with `{ctx.clean_prefix}aiuser memory toggle` "
                    "for this tool call to have an impact!"
                ),
                color=await ctx.embed_color(),
            )
            await ctx.send(embed=embed)
