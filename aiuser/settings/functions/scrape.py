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

    @functions_scrape.command(name="toggle")
    async def scrape_toggle(self, ctx: commands.Context):
        """Toggle the scrape function on or off."""
        guild_conf = self.config.guild(ctx.guild)
        enabled_tools: list = await guild_conf.function_calling_functions() or []
        enabling = names.OPEN_URL not in enabled_tools

        if enabling:
            provider = await guild_conf.function_calling_scrape_provider()
            if provider == FIRECRAWL:
                key_error = await provider_key_error(self.bot, ctx, provider)
                if key_error:
                    return await ctx.send(key_error)

        await self.toggle_function_group(ctx, [names.OPEN_URL], "Scrape")

    @functions_scrape.command(name="provider")
    async def scrape_provider(self, ctx: commands.Context, provider: str):
        """Set the scrape provider.

        Available providers: `local`, `firecrawl`
        """
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
