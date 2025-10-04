from redbot.core import commands

from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions


class WeatherFunctionSettings(FunctionToggleHelperMixin):
    @functions.group(name="weather")
    async def weather(self, ctx: commands.Context):  # type: ignore[override]
        """Weather function settings (per server)
        """
        pass

    @weather.command(name="toggle")
    async def weather_toggle(self, ctx: commands.Context):
        """Toggle the default weather functions."""
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall,
            LocationWeatherToolCall,
        )
        tool_names = [LocationWeatherToolCall.function_name, IsDaytimeToolCall.function_name]
        await self.toggle_function_group(ctx, tool_names, "Weather")

    @weather.command(name="location")
    async def weather_toggle_location(self, ctx: commands.Context):
        """Toggle the get_weather function call.
        Get the weather forecast for a specified location."""
        from aiuser.functions.weather.tool_call import LocationWeatherToolCall
        await self.toggle_single_function(ctx, LocationWeatherToolCall.function_name, "get_weather")

    @weather.command(name="daytime")
    async def weather_toggle_daytime(self, ctx: commands.Context):
        """Toggle the is_daytime function call.
        Checks if it's currently daytime at a specified location."""
        from aiuser.functions.weather.tool_call import IsDaytimeToolCall
        await self.toggle_single_function(ctx, IsDaytimeToolCall.function_name, "is_daytime")
