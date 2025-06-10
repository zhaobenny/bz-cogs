import logging
from typing import Optional

from discord.ext import commands
from openai import AsyncOpenAI
from redbot.core import Config
from redbot.core.bot import Red
from redbot.core.i18n import Translator

_ = Translator("AIEmote", __file__)

logger = logging.getLogger("red.bz_cogs.aiemote")
OPENROUTER_URL = "https://openrouter.ai"


async def setup_openai_client(
    bot: Red,
    config: Config,
    ctx: Optional[commands.Context] = None
) -> Optional[AsyncOpenAI]:
    """Initialize the OpenAI client with appropriate configuration."""
    base_url = await config.custom_openai_endpoint()
    api_type = "openai"
    api_key = None
    headers = None

    if base_url and str(base_url).startswith(OPENROUTER_URL):
        api_type = "openrouter"
        api_key = (await bot.get_shared_api_tokens(api_type)).get("api_key")
        headers = {
            "HTTP-Referer": "https://aiuser.zhao.gg",
            "X-Title": "aiemote",
        }
    else:
        api_key = (await bot.get_shared_api_tokens("openai")).get("api_key")

    if not api_key and (not base_url or api_type == "openrouter"):
        if ctx:
            error_message = _(
                "{api_type} API key not set for `aiemote`. "
                "Please set it with `{prefix}set api {api_type} api_key,[API_KEY_HERE]`"
            ).format(
                api_type=api_type,
                prefix=ctx.clean_prefix
            )
            await ctx.send(error_message)
            return None
        else:
            logger.error(
                _('{api_type} API key not set for "aiemote" yet! '
                  'Please set it with: [p]set api {api_type} api_key,[API_KEY_HERE]').format(
                    api_type=api_type
                )
            )
            return None

    return AsyncOpenAI(
        api_key=api_key or "sk-placeholderkey",
        base_url=base_url,
        timeout=15.0,
        default_headers=headers
    )