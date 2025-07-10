import json
import logging
import random
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from discord.ext import commands
from openai import AsyncOpenAI
from redbot.core import Config
from redbot.core.bot import Red

from ..config.constants import OPENROUTER_URL

logger = logging.getLogger("red.bz_cogs.aiuser")


async def setup_openai_client(
    bot: Red, config: Config, ctx: Optional[commands.Context] = None
) -> Optional[AsyncOpenAI]:
    """Initialize the OpenAI client with appropriate configuration.

    Args:
        bot: The Red bot instance
        config: The cog's Config instance
        ctx: Optional context for error messaging

    Returns:
        AsyncOpenAI client if successful, None otherwise
    """
    base_url = await config.custom_openai_endpoint()
    api_type = "openai"
    api_key = None
    headers = None

    if base_url and str(base_url).startswith(OPENROUTER_URL):
        api_type = "openrouter"
        api_key = (await bot.get_shared_api_tokens(api_type)).get("api_key")
        headers = {
            "HTTP-Referer": "https://aiuser.zhao.gg",
            "X-Title": "aiuser",
        }
    else:
        api_key = (await bot.get_shared_api_tokens("openai")).get("api_key")

    if not api_key and (not base_url or api_type == "openrouter"):
        if ctx:
            error_message = (
                f"{api_type} API key not set for `aiuser`. "
                f"Please set it with `{ctx.clean_prefix}set api {api_type} api_key,[API_KEY_HERE]`"
            )
            await ctx.send(error_message)
            return None
        else:
            logger.error(
                f'{api_type} API key not set for "aiuser" yet! '
                f"Please set it with: [p]set api {api_type} api_key,[API_KEY_HERE]"
            )
            return None

    timeout = await config.openai_endpoint_request_timeout()
    client = httpx.AsyncClient(
        event_hooks={"request": [log_request_prompt], "response": [create_ratelimit_hook(config)]}
    )

    return AsyncOpenAI(
        api_key=api_key or "sk-placeholderkey",
        base_url=base_url,
        timeout=timeout,
        default_headers=headers,
        http_client=client,
    )


async def log_request_prompt(request: httpx.Request) -> None:
    """Log the request prompt for debugging purposes."""
    if not logger.isEnabledFor(logging.DEBUG):
        return

    endpoint = request.url.path.split("/")[-1]
    if endpoint != "completions":
        return

    try:
        bytes = await request.aread()
        request_data = json.loads(bytes.decode("utf-8"))
        messages = request_data.get("messages", {})
        if not messages:
            return

        # Truncate messages image uri
        last = messages[-1]
        if isinstance(last.get("content"), list):
            for content_item in last["content"]:
                if "image_url" in content_item:
                    image_url = content_item["image_url"]["url"]
                    point = image_url.find(";base64,") + len(";base64,")
                    short_data = image_url[point : point + 20] + "..."
                    content_item["image_url"]["url"] = f"data:{image_url[:point]}{short_data}"

        logger.debug(f"Sending request with prompt: \n{json.dumps(messages, indent=4)}")
    except Exception as e:
        logger.debug(f"Error logging request prompt: {e}")


def create_ratelimit_hook(config: Config) -> Callable[[httpx.Response], None]:
    """Create a hook function for handling rate limit responses.

    Args:
        config: The cog's Config instance

    Returns:
        A hook function that updates rate limit information
    """

    async def update_ratelimit_hook(response: httpx.Response) -> None:
        if not str(response.url).startswith("https://api.openai.com/"):
            return

        headers = response.headers
        remaining_requests = float(headers.get("x-ratelimit-remaining-requests", 1))
        remaining_tokens = float(headers.get("x-ratelimit-remaining-tokens", 1))

        timestamp = datetime.now()

        if remaining_requests == 0:
            request_reset_time = extract_time_delta(headers.get("x-ratelimit-reset-requests"))
            timestamp = max(timestamp, datetime.now() + request_reset_time)
        elif remaining_tokens == 0:
            tokens_reset_time = extract_time_delta(headers.get("x-ratelimit-reset-tokens"))
            timestamp = max(timestamp, datetime.now() + tokens_reset_time)

        if remaining_requests == 0 or remaining_tokens == 0:
            logger.warning(
                f"OpenAI ratelimit reached! Next ratelimit reset at {timestamp}. "
                "(Try a non-trial key)"
            )
            await config.ratelimit_reset.set(timestamp.strftime("%Y-%m-%d %H:%M:%S"))

    return update_ratelimit_hook


def extract_time_delta(time_str: Optional[str]) -> timedelta:
    """Extract timedelta from OpenAI's ratelimit time format.

    Args:
        time_str: Time string in OpenAI format (e.g., "1d", "2h", "30m", "45s")

    Returns:
        timedelta object representing the time
    """
    if not time_str:
        return timedelta(seconds=5)

    days, hours, minutes, seconds = 0, 0, 0, 0

    if time_str.endswith("ms"):
        time_str = time_str[:-2]
        seconds += 1

    components = time_str.split("d")
    if len(components) > 1:
        days = float(components[0])
        time_str = components[1]

    components = time_str.split("h")
    if len(components) > 1:
        hours = float(components[0])
        time_str = components[1]

    components = time_str.split("m")
    if len(components) > 1:
        minutes = float(components[0])
        time_str = components[1]

    components = time_str.split("s")
    if len(components) > 1:
        seconds = float(components[0])

    seconds += random.randint(2, 3)

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
