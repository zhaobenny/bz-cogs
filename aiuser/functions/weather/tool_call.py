from typing import Any, Dict, Optional

from aiuser.functions import names
from aiuser.functions.context import ToolContext
from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.functions.weather import query

location_weather_schema = ToolCallSchema(
    function=Function(
        name=names.GET_WEATHER,
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
            required=["location"],
        ),
    )
)


class LocationWeatherToolCall(ToolCall):
    schema = location_weather_schema
    function_name = schema.function.name
    parallel_safe = True

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        days = arguments.get("days", 1)
        return await query.get_weather(arguments["location"], days=days)


class IsDaytimeToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name=names.IS_DAYTIME,
            description="Checks if it is currently daytime or nighttime at the provided location",
            parameters=Parameters(
                properties={
                    "location": {
                        "type": "string",
                        "description": "The location to check the daytime status of",
                    }
                },
                required=["location"],
            ),
        )
    )
    function_name = schema.function.name
    parallel_safe = True

    async def _handle(
        self, tool_context: ToolContext, arguments: Dict[str, Any]
    ) -> Optional[str]:
        return await query.is_daytime(arguments["location"])
