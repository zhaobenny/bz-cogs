import discord
from redbot.core import commands

from aiuser.functions import names
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class WeatherFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="weather")
    async def weather(self, ctx: commands.Context):  # type: ignore[override]
        """Weather function settings (per server)"""
        pass

    @weather.command(name="show")
    async def weather_show(self, ctx: commands.Context):
        """Show weather tool settings."""
        enabled_tools = await self.config.guild(ctx.guild).function_calling_functions()
        embed = discord.Embed(
            title="Weather tool settings", color=await ctx.embed_color()
        )
        embed.add_field(
            name="Forecasts",
            value="Enabled" if names.GET_WEATHER in enabled_tools else "Disabled",
        )
        embed.add_field(
            name="Daytime",
            value="Enabled" if names.IS_DAYTIME in enabled_tools else "Disabled",
        )
        return await ctx.send(embed=embed)

    @weather.command(name="enable")
    async def weather_enable(self, ctx: commands.Context):
        """Enable all weather tools."""
        await self.set_function_group(
            ctx, [names.GET_WEATHER, names.IS_DAYTIME], "Weather", True
        )

    @weather.command(name="disable")
    async def weather_disable(self, ctx: commands.Context):
        """Disable all weather tools."""
        await self.set_function_group(
            ctx, [names.GET_WEATHER, names.IS_DAYTIME], "Weather", False
        )

    @weather.group(name="location")
    async def weather_location(self, _):
        """Configure the location forecast tool."""
        pass

    @weather_location.command(name="enable")
    async def weather_location_enable(self, ctx: commands.Context):
        """Enable location weather forecasts."""
        await self.set_function_group(
            ctx, [names.GET_WEATHER], "Weather forecast", True
        )

    @weather_location.command(name="disable")
    async def weather_location_disable(self, ctx: commands.Context):
        """Disable location weather forecasts."""
        await self.set_function_group(
            ctx, [names.GET_WEATHER], "Weather forecast", False
        )

    @weather.group(name="daytime")
    async def weather_daytime(self, _):
        """Configure the daytime lookup tool."""
        pass

    @weather_daytime.command(name="enable")
    async def weather_daytime_enable(self, ctx: commands.Context):
        """Enable daytime lookups."""
        await self.set_function_group(ctx, [names.IS_DAYTIME], "Daytime lookup", True)

    @weather_daytime.command(name="disable")
    async def weather_daytime_disable(self, ctx: commands.Context):
        """Disable daytime lookups."""
        await self.set_function_group(ctx, [names.IS_DAYTIME], "Daytime lookup", False)
