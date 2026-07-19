import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class MemoryFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="memory", invoke_without_command=True)
    async def memory_function(self, ctx: commands.Context):
        """Show whether the memory tools are enabled."""
        return await self.show_function_group(
            ctx, [names.SAVE_MEMORY, names.READ_MEMORY], "Memory"
        )

    @memory_function.command(name="enable")
    async def enable_memory_function(self, ctx: commands.Context):
        """Allow the model to read and save memories."""
        guild_conf = self.config.guild(ctx.guild)
        querying_disabled = not await guild_conf.query_memories()

        await self.set_function_group(
            ctx, [names.SAVE_MEMORY, names.READ_MEMORY], "Memory", True
        )

        if querying_disabled:
            embed = discord.Embed(
                title=":warning: Saved memory querying is still off",
                description=(
                    f"Enable it with `{ctx.clean_prefix}aiuser memory enable` "
                    "for this tool call to have an impact!"
                ),
                color=await ctx.embed_color(),
            )
            await ctx.send(embed=embed)

    @memory_function.command(name="disable")
    async def disable_memory_function(self, ctx: commands.Context):
        """Prevent the model from reading or saving memories."""
        return await self.set_function_group(
            ctx, [names.SAVE_MEMORY, names.READ_MEMORY], "Memory", False
        )
