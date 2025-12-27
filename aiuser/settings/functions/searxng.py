import discord
from redbot.core import commands

from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class SearXNGFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="searxng")
    async def searxng(self, ctx: commands.Context):
        """Change the SearXNG setting

        (All subcommands are per server)
        """
        pass

    @searxng.command(name="toggle")
    async def searxng_toggle(self, ctx: commands.Context):
        """Toggle the SearXNG request function on or off"""
        from aiuser.functions.searxng.tool_call import SearXNGToolCall

        await self.toggle_function_group(
            ctx, [SearXNGToolCall.function_name], "SearXNG"
        )

    @searxng.command(name="endpoint")
    async def searxng_endpoint(self, ctx: commands.Context, url: str):
        """Sets the SearXNG endpoint url

        **Arguments:**
        - `url`: The url to set the endpoint to.
        """
        embed = discord.Embed(title="SearXNG endpoint", color=await ctx.embed_color())

        await self.config.guild(ctx.guild).function_calling_searxng_url.set(url)

        if url:
            embed.description = f"Endpoint set to {url}."
        else:
            embed.description = "Endpoint not set."

        await ctx.send(embed=embed)

    @searxng.command(name="results")
    async def searxng_max_results(self, ctx: commands.Context, results: int):
        """Sets the max results for the SearXNG endpoint"""

        if results < 1:
            return await ctx.send(":warning: Please enter a positive integer.")

        await self.config.guild(ctx.guild).function_calling_searxng_max_results.set(
            results
        )

        embed = discord.Embed(
            title="The max results is now:",
            description=f"`{results}` results",
            color=await ctx.embed_color(),
        )
        return await ctx.send(embed=embed)

    @searxng.command(name="show")
    async def searxng_show_config(self, ctx: commands.Context):
        """Shows the SearXNG settings."""

        endpoint = await self.config.guild(ctx.guild).function_calling_searxng_url()
        results = await self.config.guild(
            ctx.guild
        ).function_calling_searxng_max_results()

        embed = discord.Embed(
            title="SearXNG settings:",
            color=await ctx.embed_color(),
        )
        embed.add_field(
            name="SearXNG endpoint:",
            value=f"`{endpoint}`",
            inline=True,
        )
        embed.add_field(
            name="SearXNG Max Results:",
            value=f"`{results}` result(s)",
            inline=True,
        )

        return await ctx.send(embed=embed)
