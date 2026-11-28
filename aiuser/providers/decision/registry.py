from __future__ import annotations

from typing import TYPE_CHECKING

from aiuser.config.constants import DECISION_REQUEST_TIMEOUT
from aiuser.providers.decision.base import DecisionProvider
from aiuser.providers.decision.openai import OpenAIDecisionProvider
from aiuser.providers.decision.openrouter import OpenRouterDecisionProvider
from aiuser.providers.decision.typesafe import TypeSafeDecisionProvider
from aiuser.providers.llm.codex.chatgpt import CODEX_ENDPOINT_MODE
from aiuser.providers.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)

if TYPE_CHECKING:
    from aiuser.core.services import AIUserServices

DECISION_PROVIDERS: dict[str, type[DecisionProvider]] = {
    "openrouter": OpenRouterDecisionProvider,
    "openai": OpenAIDecisionProvider,
    "typesafe": TypeSafeDecisionProvider,
}


async def resolve_decision_provider_name(services: AIUserServices) -> str | None:
    """Return the active decision provider name without cross-provider fallback.

    - Explicit ``decision_provider`` config wins when set.
    - Otherwise, matches the active chat endpoint's own provider
      (``openrouter`` -> ``openrouter``; ``openai`` / ``codex`` -> ``openai``).
      Custom endpoints return ``None`` unless an explicit override is set.
    """
    explicit = await services.config.decision_provider()
    if explicit:
        normalized = str(explicit).strip().lower()
        return normalized if normalized in DECISION_PROVIDERS else None

    endpoint = await services.config.custom_openai_endpoint()
    if endpoint == CODEX_ENDPOINT_MODE:
        return "openai"

    kind = get_openai_compat_kind(endpoint)
    if kind is CompatEndpointKind.OPENROUTER:
        return "openrouter"
    if kind is CompatEndpointKind.OPENAI:
        return "openai"
    return None


async def resolve_decision_provider(
    services: AIUserServices,
) -> tuple[DecisionProvider, str] | None:
    """Resolve the active decision backend and model.

    Never silently falls back across providers: uses either the explicit
    ``decision_provider`` override or the chat endpoint's own provider.
    """
    provider_name = await resolve_decision_provider_name(services)
    if provider_name is None:
        return None

    tokens = await services.bot.get_shared_api_tokens(provider_name)
    api_key = tokens.get("api_key") if isinstance(tokens, dict) else None
    if not api_key:
        return None

    timeout = min(
        await services.config.openai_endpoint_request_timeout()
        or DECISION_REQUEST_TIMEOUT,
        DECISION_REQUEST_TIMEOUT,
    )
    provider_cls = DECISION_PROVIDERS[provider_name]
    provider = provider_cls(api_key, timeout=timeout)

    override_model = await services.config.decision_model()
    model = override_model or provider.default_model
    return provider, model
