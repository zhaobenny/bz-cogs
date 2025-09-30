import discord
from redbot.core import checks, commands

from aiuser.types.abc import MixinMeta, aiuser


class FunctionsGroupMixin(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def functions(self, ctx: commands.Context):  # type: ignore[override]
        """Settings to manage function calling

        (All subcommands are per server)
        """
        pass

# Provide a module-level alias so other settings modules can use `@functions.command(...)`
# during class body execution (the class attribute on the mixin isn't in the module scope).
functions = FunctionsGroupMixin.functions

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

    async def toggle_single_function(self, ctx: commands.Context, tool_name: str, display_name: str):  # type: ignore[override]
        """Toggle a single function/tool on or off.

        Args:
            ctx: Redbot command context.
            tool_name: Internal function identifier.
            display_name: Human friendly display name for embeds.
        """
        enabled_tools: list = await self.config.guild(ctx.guild).function_calling_functions()
        if tool_name in enabled_tools:
            enabled_tools.remove(tool_name)
            new_state = False
        else:
            enabled_tools.append(tool_name)
            new_state = True
        await self.config.guild(ctx.guild).function_calling_functions.set(enabled_tools)
        embed = discord.Embed(
            title=f"{display_name} function calling now set to:",
            description=f"{new_state}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
