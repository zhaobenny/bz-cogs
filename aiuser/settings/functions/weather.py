from redbot.core import commands

from aiuser.functions import names
from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class WeatherFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="weather")
    async def weather(self, ctx: commands.Context):  # type: ignore[override]
        """Weather function settings (per server)"""
        pass

    @weather.command(name="toggle")
    async def weather_toggle(self, ctx: commands.Context):
        """Toggle the weather functions."""
        await self.toggle_function_group(
            ctx, [names.GET_WEATHER, names.IS_DAYTIME], "Weather"
        )

    @weather.command(name="location")
    async def weather_toggle_location(self, ctx: commands.Context):
        """Toggle the get_weather function call.
        Get the weather forecast for a specified location."""
        await self.toggle_single_function(ctx, names.GET_WEATHER, "get_weather")

    @weather.command(name="daytime")
    async def weather_toggle_daytime(self, ctx: commands.Context):
        """Toggle the is_daytime function call.
        Checks if it's currently daytime at a specified location."""
        await self.toggle_single_function(ctx, names.IS_DAYTIME, "is_daytime")
