import logging
from typing import TYPE_CHECKING, Optional

import httpx
from openai import AsyncOpenAI
from redbot.core import Config
from redbot.core.bot import Red

from aiuser.providers.llm.codex.oauth import is_codex_endpoint_mode
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_api_token_name,
    get_openai_compat_kind,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

logger = logging.getLogger("red.bz_cogs.aiuser.providers.llm")


async def get_openai_client(services: "AIUserServices") -> Optional[AsyncOpenAI]:
    if services.openai_client is None:
        services.openai_client = await setup_openai_client(
            services.bot, services.config
        )
    return services.openai_client


async def invalidate_openai_client(services: "AIUserServices") -> None:
    old = services.openai_client
    services.openai_client = None
    if old:
        await old.close()


async def setup_openai_client(
    bot: Red,
    config: Config,
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
            "X-OpenRouter-Title": "aiuser",
        }
    else:
        api_key = (await bot.get_shared_api_tokens("openai")).get("api_key")

    if not api_key and (not base_url or api_type == "openrouter"):
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
