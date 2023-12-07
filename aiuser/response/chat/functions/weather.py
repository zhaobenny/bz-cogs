
import logging

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


async def get_weather(location: str):
    try:
        lat, lon = await find_lat_lon(location)
    except:
        logger.exception(f"Failed request to determine lat/lon for location {location}")
        return f"Unable to find weather for the location {location}"
    return await request_weather(lat, lon, location)


async def get_local_weather(config: Config, ctx: commands.Context):
    location = await (config.guild(ctx.guild).function_calling_weather_default_location())
    lat, lon = location
    return await request_weather(lat, lon, "current location")


async def is_daytime(config: Config, ctx: commands.Context):
    location = await (config.guild(ctx.guild).function_calling_weather_default_location())
    lat, lon = location
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "is_day",
        "forecast_days": 1
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(METEO_WEATHER_URL, params=params) as res:
                res.raise_for_status()
                weather = await res.json()
                is_day = weather['current']['is_day']
                if is_day:
                    return "Use the following infomation about your location to generate your response: It's daytime."
                else:
                    return "Use the following infomation about your location to generate your response: It's nighttime."
    except:
        logger.exception("Failed request to open-meteo.com")
        return "Unknown if it's daytime or nighttime."


async def request_weather(lat, lon, location):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["apparent_temperature", "weather_code"],
        "daily": "weather_code",
        "forecast_days": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(METEO_WEATHER_URL, params=params) as res:
                res.raise_for_status()
                weather = await res.json()

                current_weather_code = weather['current']['weather_code']
                current_weather_description = WMO_DESCRIPTIONS.get(current_weather_code, 'Unknown')

                daily_weather_code = weather['daily']['weather_code'][0]
                daily_weather_description = WMO_DESCRIPTIONS.get(daily_weather_code, 'Unknown')

                current_units = weather['current_units']
                apparent_temperature_unit = current_units.get('apparent_temperature', '°C')
                apparent_temperature = weather['current']['apparent_temperature']

                return f"Use the following weather report for {location} to generate your response:\n Today's forecast is {daily_weather_description}. The current weather is {current_weather_description}. The temperature currently feels like {apparent_temperature}{apparent_temperature_unit}."
    except:
        logger.exception("Failed request to open-meteo.com")
        return f"Could not get weather data at {location}"


async def find_lat_lon(location: str):
    params = {
        "name": location,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(METEO_GEOCODE_URL, params=params) as res:
            res.raise_for_status()

            res = await res.json()

            if not location:
                raise Exception("Location not found")
            location = res['results'][0]

            return location['latitude'], location['longitude']
