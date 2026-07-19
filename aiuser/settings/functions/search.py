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

    @functions_search.command(name="enable")
    async def search_enable(self, ctx: commands.Context):
        """Enable the web search tool"""
        guild_conf = self.config.guild(ctx.guild)
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
                f"SearXNG endpoint not set! Set it using `{ctx.clean_prefix}aiuser tools search endpoint set <url>`."
            )

        return await self.set_function_group(ctx, [names.SEARCH_WEB], "Search", True)

    @functions_search.command(name="disable")
    async def search_disable(self, ctx: commands.Context):
        """Disable the web search tool"""
        return await self.set_function_group(ctx, [names.SEARCH_WEB], "Search", False)

    @functions_search.group(name="provider", invoke_without_command=True)
    async def search_provider(self, ctx: commands.Context):
        """Show the web search provider"""
        provider = await self.config.guild(ctx.guild).function_calling_search_provider()
        return await ctx.maybe_send_embed(f"Search provider: `{provider}`")

    @search_provider.command(name="set")
    async def search_provider_set(self, ctx: commands.Context, provider: str):
        """Set the web search provider"""
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
                text=f"⚠️ Set the SearXNG endpoint using {ctx.clean_prefix}aiuser tools search endpoint set <url>"
            )
        await ctx.send(embed=embed)

    @functions_search.group(name="endpoint", invoke_without_command=True)
    async def search_endpoint(self, ctx: commands.Context):
        """Show the SearXNG endpoint"""
        url = await self.config.guild(ctx.guild).function_calling_search_endpoint()
        return await ctx.maybe_send_embed(f"Search endpoint: `{url or 'Not set'}`")

    @search_endpoint.command(name="set")
    async def search_endpoint_set(self, ctx: commands.Context, url: str):
        """Set the SearXNG endpoint"""
        await self.config.guild(ctx.guild).function_calling_search_endpoint.set(url)
        return await ctx.send(f"Search endpoint set to `{url}`.")

    @search_endpoint.command(name="clear")
    async def search_endpoint_clear(self, ctx: commands.Context):
        """Clear the SearXNG endpoint"""
        await self.config.guild(ctx.guild).function_calling_search_endpoint.set(None)
        return await ctx.send("Search endpoint cleared.")

    @functions_search.group(name="results", invoke_without_command=True)
    async def search_max_results(self, ctx: commands.Context):
        """Show the maximum search results"""
        results = await self.config.guild(
            ctx.guild
        ).function_calling_search_max_results()
        return await ctx.maybe_send_embed(f"Maximum search results: `{results}`")

    @search_max_results.command(name="set")
    async def search_max_results_set(self, ctx: commands.Context, results: int):
        """Set the maximum search results"""
        if results < 1:
            return await ctx.send(":warning: Please enter a positive integer.")

        await self.config.guild(ctx.guild).function_calling_search_max_results.set(
            results
        )

        return await ctx.send(f"Maximum search results set to `{results}`.")

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
