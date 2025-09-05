
import discord
from redbot.core import checks, commands

from aiuser.types.abc import MixinMeta, aiuser


class FunctionCallingSettings(MixinMeta):
    @aiuser.group()
    @checks.is_owner()
    async def functions(self, _):
        """ Settings to manage function calling

            (All subcommands are per server)
        """
        pass

    @functions.command(name="toggle")
    async def toggle_function_calling(self, ctx: commands.Context):
        """Toggle functions calling

        Requires a model that is whitelisted or supported for function calling
        If enabled, the LLM will call functions to generate responses when needed
        This will generate additional API calls and token usage!

        """

        current_value = not await self.config.guild(ctx.guild).function_calling()
        await self.config.guild(ctx.guild).function_calling.set(current_value)

        embed = discord.Embed(
            title="🔀 Functions Calling now set to:",
            description=f"{current_value}",
            color=await ctx.embed_color(),
        )
        if current_value:
            embed.set_footer(text="⚠️ Ensure selected model supports function calling!")
        await ctx.send(embed=embed)

    @functions.command(name="location")
    async def set_location(self, ctx: commands.Context, latitude: float, longitude: float):
        """ Set the location where the bot will canonically be in

            Used for some functions.

            **Arguments**
            - `latitude` decimal latitude
            - `longitude` decimal longitude
        """
        await self.config.guild(ctx.guild).function_calling_default_location.set([latitude, longitude])
        embed = discord.Embed(
            title="📍 Location now set to:",
            description=f"{latitude}, {longitude}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    async def toggle_function_helper(self, ctx: commands.Context, tool_names: list, embed_title: str):
        enabled_tools: list = await self.config.guild(ctx.guild).function_calling_functions()

        if tool_names[0] not in enabled_tools:
            enabled_tools.extend(tool_names)
        else:
            for tool in tool_names:
                enabled_tools.remove(tool)

        await self.config.guild(ctx.guild).function_calling_functions.set(enabled_tools)

        embed = discord.Embed(
            title=f"Tool calling for {embed_title} now set to:",
            description=f"{tool_names[0] in enabled_tools}",
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @functions.command(name="search")
    async def toggle_search_function(self, ctx: commands.Context):
        """ Enable/disable searching/scraping the Internet using Serper.dev """
        if (not (await self.bot.get_shared_api_tokens("serper")).get("api_key")):
            return await ctx.send(f"Serper.dev key not set! Set it using `{ctx.clean_prefix}set api serper api_key,APIKEY`.")

        from aiuser.functions.search.tool_call import SearchToolCall

        tool_names = [SearchToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "🔎 Search")

    @functions.command(name="scrape")
    async def toggle_scrape_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to open URLs in messages

        (May not be called if the link generated an Discord embed)
        """
        from aiuser.functions.scrape.tool_call import ScrapeToolCall

        tool_names = [ScrapeToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "📜 Scrape")

    @functions.command(name="weather")
    async def toggle_weather_function(self, ctx: commands.Context):
        """ Enable/disable a group of functions to getting weather using Open-Meteo

            See [Open-Meteo terms](https://open-meteo.com/en/terms) for their free API
        """
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall,
            LocalWeatherToolCall,
            LocationWeatherToolCall,
        )

        tool_names = [IsDaytimeToolCall.function_name,
                      LocalWeatherToolCall.function_name, LocationWeatherToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "🌦️ Weather")

    @functions.command(name="noresponse")
    async def toggle_ignore_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to choose to not respond and ignore messages.

        Temperamental, may require additional prompting to work better.
        """
        from aiuser.functions.noresponse.tool_call import NoResponseToolCall

        tool_names = [NoResponseToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "🤫 No response")

    @functions.command(name="wolframalpha")
    async def toggle_wolfram_alpha_function(self, ctx: commands.Context):
        """ Enable/disable the functionality for the LLM to ask Wolfram Alpha about math, exchange rates, or the weather."""
        from aiuser.functions.wolframalpha.tool_call import WolframAlphaFunctionCall

        if (not (await self.bot.get_shared_api_tokens("wolfram_alpha")).get("app_id")):
            return await ctx.send(f"Wolfram Alpha app id not set! Set it using `{ctx.clean_prefix}set api wolfram_alpha app_id,APPID`.")

        tool_names = [WolframAlphaFunctionCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "🐺 Wolfram Alpha")
