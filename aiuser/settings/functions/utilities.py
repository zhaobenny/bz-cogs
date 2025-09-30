import discord
from redbot.core import commands

from aiuser.types.abc import MixinMeta, aiuser


@aiuser.group(name="functions")
async def functions(self, _):
    """Settings to manage function calling"""
    pass

class FunctionToggleHelperMixin(MixinMeta):
    async def toggle_function_helper(self, ctx: commands.Context, tool_names: list, embed_title: str):  # type: ignore[override]
        """Toggle one or more tool names on/off for the guild.

        Args:
            ctx: Redbot command invocation context.
            tool_names: List of internal function/tool identifiers to toggle together.
            embed_title: Human friendly title for the resulting embed.
        """
        enabled_tools: list = await self.config.guild(ctx.guild).function_calling_functions()

        if tool_names and tool_names[0] not in enabled_tools:
            # Enable all tools in the group
            enabled_tools.extend(tool_names)
        else:
            # Disable all tools in the group
            for tool in tool_names:
                if tool in enabled_tools:
                    enabled_tools.remove(tool)

        await self.config.guild(ctx.guild).function_calling_functions.set(enabled_tools)

        embed = discord.Embed(
            title=f"{embed_title} function calling now set to:",
            description=f"{bool(tool_names and tool_names[0] in enabled_tools)}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
