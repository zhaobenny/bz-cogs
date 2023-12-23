
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Parameters:
    properties: dict
    required: list[str] = field(default_factory=list)
    type: str = "object"


@dataclass(frozen=True)
class Function:
    name: str
    description: str
    parameters: Parameters


@dataclass(frozen=True)
class ToolCall:
    function: Function
    type: str = "function"

    def __hash__(self):
        return hash(self.function.name + self.function.description)


SERPER_SEARCH = ToolCall(function=Function(
    name="search_google",
    description="Searches Google using the query for any unknown information or most current infomation",
    parameters=Parameters(
        properties={
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
        },
        required=["query"]
    )))

LOCAL_WEATHER = ToolCall(function=Function(
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


LOCATION_WEATHER = ToolCall(function=Function(
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

IS_DAYTIME = ToolCall(function=Function(
    name="is_daytime_local",
    description="Checks if it is daytime or nighttime in the local location you are in",
    parameters=Parameters(
        properties={}
    )
))
