from __future__ import annotations

from typing import Optional

import discord
from redbot.core import checks, commands
from redbot.core.bot import Red

from aiuser.settings._groups import aiuser
from aiuser.types.abc import MixinMeta


async def provider_key_error(
    bot: Red, ctx: commands.Context, provider: str, key_name: str = "api_key"
) -> Optional[str]:
    """Return an error string if *provider* has no *key_name* token set, else None.

    Args:
        bot: The Red bot instance.
        ctx: Redbot command invocation context (used for clean_prefix).
        provider: The shared-API-token service name (e.g. ``"exa"``).
        key_name: The token field name to check (default ``"api_key"``).
    """
    tokens = await bot.get_shared_api_tokens(provider)
    if tokens.get(key_name):
        return None
    return (
        f"{provider} {key_name} not set! Set it using "
        f"`{ctx.clean_prefix}set api {provider} {key_name},VALUE`."
    )


class FunctionsGroupMixin(MixinMeta):
    @aiuser.group(name="tools", aliases=["functions"])
    @checks.is_owner()
    async def functions(self, ctx: commands.Context):
        """Configure tools the model can use

        (All subcommands are per server)
        """
        pass


# Module-level alias of the group stub so sibling settings modules can write
# `@functions.command(...)` at class-body time.
functions = FunctionsGroupMixin.functions


class FunctionToggleHelperMixin(MixinMeta):
    async def set_function_group(
        self,
        ctx: commands.Context,
        tool_names: list,
        embed_title: str,
        enabled: bool,
    ):
        """Enable or disable a group of related tools for the guild.

        Args:
            ctx: Redbot command invocation context.
            tool_names: List of internal function/tool identifiers to toggle together.
            embed_title: Human friendly title for the resulting embed.
            enabled: Whether the tools should be enabled.
        """
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions() or []

        if enabled:
            enabled_tools.extend(
                name for name in tool_names if name not in enabled_tools
            )
            await guild_conf.function_calling.set(True)
        else:
            enabled_tools = [name for name in enabled_tools if name not in tool_names]

        await guild_conf.function_calling_functions.set(enabled_tools)

        embed = discord.Embed(
            title=f"{embed_title} tool is now:",
            description="Enabled" if enabled else "Disabled",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    async def show_function_group(
        self, ctx: commands.Context, tool_names: list, embed_title: str
    ):
        enabled_tools: list = await self.config.guild(
            ctx.guild
        ).function_calling_functions()
        enabled = all(name in enabled_tools for name in tool_names)
        return await ctx.maybe_send_embed(
            f"{embed_title} tool: `{'Enabled' if enabled else 'Disabled'}`"
        )
