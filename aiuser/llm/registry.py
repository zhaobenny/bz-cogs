from typing import TYPE_CHECKING, Optional

from aiuser.llm.codex.oauth import is_codex_endpoint_mode
from aiuser.llm.codex.provider import CodexProvider
from aiuser.llm.openai_compatible.client import setup_openai_client
from aiuser.llm.openai_compatible.provider import OpenAICompatibleProvider

from .base import LLMProvider

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices


async def get_llm_provider(services: "AIUserServices") -> Optional[LLMProvider]:
    if await is_codex_endpoint_mode(services.config):
        return CodexProvider(services.config)

    if services.openai_client is None:
        services.openai_client = await setup_openai_client(
            services.bot, services.config
        )

    if services.openai_client is None:
        return None

    return OpenAICompatibleProvider(services.config, services.openai_client)


async def list_llm_models(services: "AIUserServices") -> list:
    provider = await get_llm_provider(services)
    if provider is None:
        return []
    return await provider.list_models()
