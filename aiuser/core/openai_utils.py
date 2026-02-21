import json
import logging
from typing import Optional

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
        event_hooks={
            "request": [log_request_prompt],
        }
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
                    content_item["image_url"]["url"] = (
                        f"data:{image_url[:point]}{short_data}"
                    )

        logger.debug(f"Sending request with prompt: \n{json.dumps(messages, indent=4)}")
    except Exception as e:
        logger.debug(f"Error logging request prompt: {e}")
