import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.functions.scrape.providers import FIRECRAWL, PROVIDERS
from aiuser.settings.functions.utilities import (
    FunctionToggleHelperMixin,
    functions,
    provider_key_error,
)


class ScrapeFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="scrape")
    async def functions_scrape(self, ctx: commands.Context):
        """Scrape function settings (per server)."""
        pass

    @functions_scrape.command(name="show")
    async def scrape_show(self, ctx: commands.Context):
        """Show web page reading tool settings."""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        provider = await guild_conf.function_calling_scrape_provider()
        embed = discord.Embed(
            title="Web page reading tool settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Enabled", value="Yes" if names.OPEN_URL in enabled_tools else "No"
        )
        embed.add_field(name="Provider", value=f"`{provider}`")
        return await ctx.send(embed=embed)

    @functions_scrape.command(name="enable")
    async def scrape_enable(self, ctx: commands.Context):
        """Enable the web page reading tool."""
        provider = await self.config.guild(ctx.guild).function_calling_scrape_provider()
        if provider == FIRECRAWL:
            key_error = await provider_key_error(self.bot, ctx, provider)
            if key_error:
                return await ctx.send(key_error)
        return await self.set_function_group(ctx, [names.OPEN_URL], "Scrape", True)

    @functions_scrape.command(name="disable")
    async def scrape_disable(self, ctx: commands.Context):
        """Disable the web page reading tool."""
        return await self.set_function_group(ctx, [names.OPEN_URL], "Scrape", False)

    @functions_scrape.group(name="provider", invoke_without_command=True)
    async def scrape_provider(self, ctx: commands.Context):
        """Show the web page reading provider"""
        provider = await self.config.guild(ctx.guild).function_calling_scrape_provider()
        return await ctx.maybe_send_embed(f"Web page reading provider: `{provider}`")

    @scrape_provider.command(name="set")
    async def scrape_provider_set(self, ctx: commands.Context, provider: str):
        """Set the web page reading provider"""
        provider = provider.strip().lower()

        if provider not in PROVIDERS:
            return await ctx.send(
                "Available scrape providers: " + ", ".join(f"`{p}`" for p in PROVIDERS)
            )

        if provider == FIRECRAWL:
            key_error = await provider_key_error(self.bot, ctx, provider)
            if key_error:
                return await ctx.send(key_error)

        await self.config.guild(ctx.guild).function_calling_scrape_provider.set(
            provider
        )

        embed = discord.Embed(
            title="Scrape provider now set to:",
            description=f"`{provider}`",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)
