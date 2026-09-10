from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse


class CompatEndpointKind(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


def get_openai_compat_kind(endpoint: str | None) -> CompatEndpointKind:
    """for completion api endpoints"""

    parsed = urlparse(str(endpoint or "").strip())
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return CompatEndpointKind.OPENAI

    if hostname == "api.openai.com":
        return CompatEndpointKind.OPENAI

    if hostname == "openrouter.ai":
        return CompatEndpointKind.OPENROUTER

    return CompatEndpointKind.CUSTOM


def get_openai_compat_api_token_name(endpoint: str | None) -> str:
    if get_openai_compat_kind(endpoint) is CompatEndpointKind.OPENROUTER:
        return "openrouter"
    return "openai"


def is_openai_endpoint(endpoint: str | None) -> bool:
    return get_openai_compat_kind(endpoint) is CompatEndpointKind.OPENAI


def is_openrouter_endpoint(endpoint: str | None) -> bool:
    return get_openai_compat_kind(endpoint) is CompatEndpointKind.OPENROUTER
