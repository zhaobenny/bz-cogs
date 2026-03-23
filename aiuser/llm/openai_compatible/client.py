import logging
from typing import Optional

import httpx
from discord.ext import commands
from openai import AsyncOpenAI
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.llm.codex.oauth import is_codex_endpoint_mode
from aiuser.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_api_token_name,
    get_openai_compat_kind,
)

logger = logging.getLogger("red.bz_cogs.aiuser.llm")


async def setup_openai_client(
    bot: Red,
    config: Config,
    ctx: Optional[commands.Context] = None,
    base_url: Optional[str] = None,
) -> Optional[AsyncOpenAI]:
    if base_url is None and await is_codex_endpoint_mode(config):
        return None

    if base_url is None:
        base_url = await config.custom_openai_endpoint()

    endpoint_kind = get_openai_compat_kind(base_url)
    api_type = get_openai_compat_api_token_name(base_url)
    api_key = None
    headers = None

    if endpoint_kind is CompatEndpointKind.OPENROUTER:
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

        logger.error(
            f'{api_type} API key not set for "aiuser" yet! '
            f"Please set it with: [p]set api {api_type} api_key,[API_KEY_HERE]"
        )
        return None

    timeout = await config.openai_endpoint_request_timeout()
    client = httpx.AsyncClient()

    return AsyncOpenAI(
        api_key=api_key or "sk-placeholderkey",
        base_url=base_url,
        timeout=timeout,
        default_headers=headers,
        http_client=client,
    )
