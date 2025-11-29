from aiuser.functions.tool_call import ToolCall
from aiuser.functions.types import Function, Parameters, ToolCallSchema
from aiuser.functions.weather.query import get_weather, is_daytime

location_weather_schema = ToolCallSchema(
    function=Function(
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
            required=["location"],
        ),
    )
)


class LocationWeatherToolCall(ToolCall):
    schema = location_weather_schema
    function_name = schema.function.name

    def remove_tool_from_available(self, available_tools: list):
        if self.schema in available_tools:
            available_tools.remove(self.schema)

    async def _handle(self, _, arguments):
        days = arguments.get("days", 1)
        return await get_weather(arguments["location"], days=days)


class IsDaytimeToolCall(ToolCall):
    schema = ToolCallSchema(
        function=Function(
            name="is_daytime",
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

    async def _handle(self, _, arguments):
        return await is_daytime(arguments["location"])
