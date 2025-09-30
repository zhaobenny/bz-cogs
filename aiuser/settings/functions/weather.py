from redbot.core import commands

from aiuser.settings.functions.utilities import FunctionToggleHelperMixin, functions
from aiuser.types.abc import MixinMeta


class WeatherFunctionSettings(MixinMeta, FunctionToggleHelperMixin):
    @functions.group(name="weather")
    async def weather(self, ctx: commands.Context):  # type: ignore[override]
        """Weather function settings (per server)
        """
        pass

    @weather.command(name="toggle")
    async def weather_toggle(self, ctx: commands.Context):
        """Toggle the default weather functions (get_weather & get_local_weather)."""
        from aiuser.functions.weather.tool_call import (
            LocalWeatherToolCall,
            LocationWeatherToolCall,
        )
        tool_names = [LocalWeatherToolCall.function_name, LocationWeatherToolCall.function_name]
        await self.toggle_function_helper(ctx, tool_names, "Weather")

    @weather.command(name="location")
    async def weather_toggle_location(self, ctx: commands.Context):
        """Toggle the get_weather function call."""
        from aiuser.functions.weather.tool_call import LocationWeatherToolCall
        await self.toggle_single_function(ctx, LocationWeatherToolCall.function_name, "get_weather")

    @weather.command(name="local")
    async def weather_toggle_local(self, ctx: commands.Context):
        """Toggle the get_local_weather function call. 
        Uses the set location as 'local'."""
        from aiuser.functions.weather.tool_call import LocalWeatherToolCall
        await self.toggle_single_function(ctx, LocalWeatherToolCall.function_name, "get_local_weather")

    @weather.command(name="daytime")
    async def weather_toggle_daytime(self, ctx: commands.Context):
        """Toggle the is_daytime_local function call.
        Checks if it's currently daytime at the set location as 'local'."""
        from aiuser.functions.weather.tool_call import IsDaytimeToolCall
        await self.toggle_single_function(ctx, IsDaytimeToolCall.function_name, "is_daytime_local")
