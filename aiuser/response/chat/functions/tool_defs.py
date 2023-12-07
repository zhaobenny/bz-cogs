SERPER_SEARCH = {
    "type": "function",
    "function": {
        "name": "search_google",
        "description": "Searches Google for the query for any unknown information or most current infomation",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    }
}

LOCAL_WEATHER = {
    "type": "function",
    "function": {
        "name": "get_local_weather",
        "description": "Get the weather of the local location you are in",
        "parameters": {
            "type": "object",
            "properties": {},
        }
    }
}

LOCATION_WEATHER = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather of a city, region, or country",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to get the weather of",
                }
            },
            "required": ["location"],
        },
    }
}

IS_DAYTIME = {
    "type": "function",
    "function": {
        "name": "is_daytime_local",
        "description": "Checks if it is daytime or nighttime in the local location you are in",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
