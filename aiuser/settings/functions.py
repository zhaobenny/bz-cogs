
import discord
from redbot.core import checks, commands

from aiuser.abc import MixinMeta, aiuser
from aiuser.common.constants import FUNCTION_CALLING_SUPPORTED_MODELS


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

        Requires a model that supports function calling
        If enabled, the LLM will call functions to generate responses when needed
        This will generate additional API calls and token usage!

        """

        current_value = not await self.config.guild(ctx.guild).function_calling()

        if current_value:
            model = await self.config.guild(ctx.guild).model()
            if model not in FUNCTION_CALLING_SUPPORTED_MODELS:
                return await ctx.send(f":warning: Currently selected model, `{model}`, does not support function calling. Set a comptaible model first!")

        await self.config.guild(ctx.guild).function_calling.set(current_value)

        embed = discord.Embed(
            title="Functions Calling now set to:",
            description=f"{current_value}",
            color=await ctx.embed_color(),
        )
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
            title="Location now set to:",
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
            title=f"{embed_title} function calling now set to:",
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

        await self.toggle_function_helper(ctx, tool_names, "Search")

    @functions.command(name="scrape")
    async def toggle_scrape_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to open URLs in messages

        (May not be called if the link generated an Discord embed)
        """
        from aiuser.functions.scrape.tool_call import ScrapeToolCall

        tool_names = [ScrapeToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "Scrape")

    @functions.command(name="weather")
    async def toggle_weather_function(self, ctx: commands.Context):
        """ Enable/disable a group of functions to getting weather using Open-Meteo

            See [Open-Meteo terms](https://open-meteo.com/en/terms) for their free API
        """
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall, LocalWeatherToolCall, LocationWeatherToolCall)

        tool_names = [IsDaytimeToolCall.function_name,
                      LocalWeatherToolCall.function_name, LocationWeatherToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "Weather")

    @functions.command(name="noresponse")
    async def toggle_ignore_function(self, ctx: commands.Context):
        """
        Enable/disable the functionality for the LLM to choose to not respond and ignore messages.

        Temperamental, may require additional prompting to work better.
        """
        from aiuser.functions.noresponse.tool_call import NoResponseToolCall

        tool_names = [NoResponseToolCall.function_name]

        await self.toggle_function_helper(ctx, tool_names, "No response")
