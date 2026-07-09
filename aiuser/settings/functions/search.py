from typing import Optional

import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.functions.search.providers import PROVIDER_KEY_SERVICES, PROVIDERS, SEARXNG
from aiuser.settings.functions.utilities import (
    FunctionToggleHelperMixin,
    functions,
    provider_key_error,
)


class SearchFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="search")
    async def functions_search(self, ctx: commands.Context):
        """Web search function settings (per server)."""
        pass

    @functions_search.command(name="toggle")
    async def search_toggle(self, ctx: commands.Context):
        """Toggle the web search function on or off"""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        enabling = names.SEARCH_WEB not in enabled_tools

        if enabling:
            provider = await guild_conf.function_calling_search_provider()
            key_service = PROVIDER_KEY_SERVICES.get(provider)
            if key_service:
                key_error = await provider_key_error(self.bot, ctx, key_service)
                if key_error:
                    return await ctx.send(key_error)
            if (
                provider == SEARXNG
                and not await guild_conf.function_calling_search_endpoint()
            ):
                return await ctx.send(
                    f"SearXNG endpoint not set! Set it using `{ctx.clean_prefix}aiuser functions search endpoint <url>`."
                )

        await self.toggle_function_group(ctx, [names.SEARCH_WEB], "Search")

    @functions_search.command(name="provider")
    async def search_provider(self, ctx: commands.Context, provider: str):
        """Set the search provider.

        Available providers: `exa`, `searxng`
        """
        provider = provider.strip().lower()

        if provider not in PROVIDERS:
            return await ctx.send(
                "Available search providers: " + ", ".join(f"`{p}`" for p in PROVIDERS)
            )

        key_service = PROVIDER_KEY_SERVICES.get(provider)
        if key_service:
            key_error = await provider_key_error(self.bot, ctx, key_service)
            if key_error:
                return await ctx.send(key_error)

        await self.config.guild(ctx.guild).function_calling_search_provider.set(
            provider
        )

        embed = discord.Embed(
            title="Search provider now set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )
        if (
            provider == SEARXNG
            and not await self.config.guild(
                ctx.guild
            ).function_calling_search_endpoint()
        ):
            embed.set_footer(
                text=f"⚠️ Set the SearXNG endpoint using {ctx.clean_prefix}aiuser functions search endpoint <url>"
            )
        await ctx.send(embed=embed)

    @functions_search.command(name="endpoint")
    async def search_endpoint(self, ctx: commands.Context, url: Optional[str] = None):
        """Sets the search endpoint url (used by the `searxng` provider)

        **Arguments:**
        - `url`: The url to set the endpoint to. Leave blank to unset.
        """
        await self.config.guild(ctx.guild).function_calling_search_endpoint.set(url)

        embed = discord.Embed(title="Search endpoint", color=await ctx.embed_color())
        if url:
            embed.description = f"Endpoint set to {url}."
        else:
            embed.description = "Endpoint not set."
        await ctx.send(embed=embed)

    @functions_search.command(name="results")
    async def search_max_results(self, ctx: commands.Context, results: int):
        """Sets the max results returned per search (used by the `searxng` provider)"""

        if results < 1:
            return await ctx.send(":warning: Please enter a positive integer.")

        await self.config.guild(ctx.guild).function_calling_search_max_results.set(
            results
        )

        embed = discord.Embed(
            title="The max results is now:",
            description=f"`{results}` results",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @functions_search.command(name="show")
    async def search_show_config(self, ctx: commands.Context):
        """Shows the web search settings."""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        provider = await guild_conf.function_calling_search_provider()
        endpoint = await guild_conf.function_calling_search_endpoint()
        results = await guild_conf.function_calling_search_max_results()

        embed = discord.Embed(
            title="Search settings:",
            color=await ctx.embed_color(),
        )
        embed.add_field(
            name="Enabled",
            value="✅" if names.SEARCH_WEB in enabled_tools else "❌",
            inline=True,
        )
        embed.add_field(name="Provider", value=f"`{provider}`", inline=True)
        embed.add_field(
            name="Endpoint", value=f"`{endpoint or 'not set'}`", inline=True
        )
        embed.add_field(name="Max Results", value=f"`{results}` result(s)", inline=True)

        return await ctx.send(embed=embed)
