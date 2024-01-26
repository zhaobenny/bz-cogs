from dataclasses import asdict

from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import (Function, Parameters,
                                                  ToolCallSchema)
from aiuser.functions.weather.query import (get_local_weather,
                                                          get_weather,
                                                          is_daytime)

location_weather_schema = ToolCallSchema(function=Function(
    name="get_weather",
    description="Get the requested weather forecast of a city, region, or country",
    parameters=Parameters(
        properties={
                "location": {
                    "type": "string",
                    "description": "The location to get the weather of",
                },
            "days": {
                    "type": "integer",
                    "description": "The number of days to get the weather of",
                    "default": 1,
                },
        },
        required=["location"]
    )
))

local_weather_schema = ToolCallSchema(function=Function(
    name="get_local_weather",
    description="Get the requested weather forecast of the local location you are in",
    parameters=Parameters(
        properties={
            "days": {
                "type": "integer",
                "description": "The number of days to get the weather of",
                "default": 1,
            }
        },
        required=[]
    )
))


class LocationWeatherToolCall(ToolCall):
    schema = location_weather_schema
    function_name = schema.function.name

    def remove_tool_from_available(self, available_tools: list):
        if self.schema in available_tools:
            available_tools.remove(self.schema)
        if local_weather_schema in available_tools:
            available_tools.remove(local_weather_schema)

    async def _handle(self, arguments):
        days = arguments.get("days", 1)
        return await get_weather(arguments["location"], days=days)


class LocalWeatherToolCall(ToolCall):
    schema = local_weather_schema
    function_name = schema.function.name

    def remove_tool_from_available(self, available_tools: list):
        if self.schema in available_tools:
            available_tools.remove(self.schema)
        if local_weather_schema in available_tools:
            available_tools.remove(location_weather_schema)

    async def _handle(self, arguments):
        days = arguments.get("days", 1)
        return await get_local_weather(self.config, self.ctx, days=days)


class IsDaytimeToolCall(ToolCall):
    schema = ToolCallSchema(function=Function(
        name="is_daytime_local",
        description="Checks if it is daytime or nighttime in the local location you are in",
        parameters=Parameters(
            properties={}
        )
    ))
    function_name = schema.function.name

    async def _handle(self, _):
        return await is_daytime(self.config, self.ctx)
