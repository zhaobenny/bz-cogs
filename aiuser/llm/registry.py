from typing import Optional

from aiuser.llm.codex.oauth import is_codex_endpoint_mode
from aiuser.llm.codex.provider import CodexProvider
from aiuser.llm.openai_compatible.client import setup_openai_client
from aiuser.llm.openai_compatible.provider import OpenAICompatibleProvider
from aiuser.types.abc import MixinMeta

from .base import LLMProvider


async def get_llm_provider(cog: MixinMeta) -> Optional[LLMProvider]:
    if await is_codex_endpoint_mode(cog.config):
        return CodexProvider(cog.config)

    if cog.openai_client is None:
        cog.openai_client = await setup_openai_client(cog.bot, cog.config)

    if cog.openai_client is None:
        return None

    return OpenAICompatibleProvider(cog.config, cog.openai_client)


async def list_llm_models(cog: MixinMeta) -> list[str]:
    provider = await get_llm_provider(cog)
    if provider is None:
        return []
    return await provider.list_models()
