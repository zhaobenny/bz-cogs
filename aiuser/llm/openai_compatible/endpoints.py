from enum import Enum
from typing import Optional
from urllib.parse import urlparse


class CompatEndpointKind(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


def get_openai_compat_kind(endpoint: Optional[str]) -> CompatEndpointKind:
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


def is_openai_endpoint(endpoint: Optional[str]) -> bool:
    return get_openai_compat_kind(endpoint) is CompatEndpointKind.OPENAI


def is_openrouter_endpoint(endpoint: Optional[str]) -> bool:
    return get_openai_compat_kind(endpoint) is CompatEndpointKind.OPENROUTER
