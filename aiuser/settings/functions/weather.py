from redbot.core import commands

from aiuser.settings.functions.utilities import functions
from aiuser.types.abc import MixinMeta


class WeatherFunctionSettings(MixinMeta):
    @functions.command(name="weather")
    async def toggle_weather_function(self, ctx: commands.Context):
        """ Enable/disable a group of functions for getting weather using Open-Meteo """
        from aiuser.functions.weather.tool_call import (
            IsDaytimeToolCall,
            LocalWeatherToolCall,
            LocationWeatherToolCall,
        )
        tool_names = [IsDaytimeToolCall.function_name,
                      LocalWeatherToolCall.function_name, LocationWeatherToolCall.function_name]
        await self.toggle_function_helper(ctx, tool_names, "Weather")
