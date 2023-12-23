
import logging
from itertools import islice

import aiohttp
from redbot.core import Config, commands

logger = logging.getLogger("red.bz_cogs.aiuser")

METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WMO_DESCRIPTIONS = {
    0: 'clear sky',
    1: 'mostly clear',
    2: 'partly cloudy',
    3: 'overcast',
    45: 'foggy with depositing frost',
    48: 'foggy with depositing frost',
    51: 'light drizzle',
    53: 'moderate drizzle',
    55: 'heavy drizzle',
    56: 'light freezing drizzle',
    57: 'heavy freezing drizzle',
    61: 'light rain',
    63: 'moderate rain',
    65: 'heavy rain',
    66: 'light freezing rain',
    67: 'heavy freezing rain',
    71: 'slight snowfall',
    73: 'moderate snowfall',
    75: 'heavy snowfall',
    77: 'snow grains',
    80: 'slight rain showers',
    81: 'moderate rain showers',
    82: 'violent rain showers',
    85: 'slight snow showers',
    86: 'heavy snow showers',
    95: 'slight or moderate thunderstorm',
    96: 'thunderstorm with slight hail',
    99: 'thunderstorm with heavy hail'
}


async def get_endpoint_data(url, params):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()


async def get_weather(location: str, days=1):
    try:
        lat, lon = await find_lat_lon(location)
    except:
        logger.exception(f"Failed request to determine lat/lon for location {location}")
        return f"Unable to find weather for the location {location}"
    return await request_weather(lat, lon, location, days=days)


async def get_local_weather(config: Config, ctx: commands.Context, days=1):
    location = await (config.guild(ctx.guild).function_calling_default_location())
    lat, lon = location
    return await request_weather(lat, lon, "current location", days=days)


async def is_daytime(config: Config, ctx: commands.Context):
    location = await (config.guild(ctx.guild).function_calling_default_location())
    lat, lon = location
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "is_day",
        "forecast_days": 1
    }
    try:
        data = await get_endpoint_data(METEO_WEATHER_URL, params)
        is_day = data['current']['is_day']
        if is_day:
            return "Use the following information about your location to generate your response: It's daytime."
        else:
            return "Use the following information about your location to generate your response: It's nighttime."
    except:
        logger.exception("Failed request to open-meteo.com")
        return "Unknown if it's daytime or nighttime."


async def request_weather(lat, lon, location, days=1):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "weather_code"],
        "daily": "weather_code",
        "forecast_days": days
    }

    try:
        data = await get_endpoint_data(METEO_WEATHER_URL, params)

        res = f"Use the following information for {location} to generate your response: \n"

        current_weather_code = data['current']['weather_code']
        current_weather_description = WMO_DESCRIPTIONS.get(current_weather_code, 'Unknown')

        res += f"The current weather is {current_weather_description}. "

        daily_weather_code = data['daily']['weather_code'][0]
        daily_weather_description = WMO_DESCRIPTIONS.get(daily_weather_code, 'Unknown')

        res += f"Today's forecast is {daily_weather_description}. "

        current_units = data['current_units']
        temperature_unit = current_units.get('temperature_2m', '°C')
        temperature = data['current']['temperature_2m']

        res += f"The temperature currently is {temperature}{temperature_unit}. "

        if days > 1:
            res += handle_multiple_days(data)

        return res
    except:
        logger.exception("Failed request to open-meteo.com")
        return f"Could not get weather data at {location}"


def handle_multiple_days(data):
    if not data.get('daily', False):
        return ""
    res = " "
    time_list = data["daily"]["time"]
    weather_code_list = data["daily"]["weather_code"]
    res += (" ".join([f"On {time}, the forecasted weather is {WMO_DESCRIPTIONS.get(code, 'unknown')}." for time,
            code in islice(zip(time_list, weather_code_list), 1, None)]))
    return res


async def find_lat_lon(location: str):
    params = {
        "name": location,
        "count": 1,
        "language": "en",
        "format": "json"
    }


    response = await get_endpoint_data(METEO_GEOCODE_URL, params)

    if not (response.get('results', False)):
        raise Exception("Location not found")

    location = response['results'][0]

    return location['latitude'], location['longitude']
