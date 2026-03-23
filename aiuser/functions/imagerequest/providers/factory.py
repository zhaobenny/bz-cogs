from urllib.parse import urlparse

from aiuser.functions.imagerequest.providers import (
    automatic1111,
    custom_http,
    gemini,
    openai,
    openrouter,
)
from aiuser.llm.openai_compatible.endpoints import (
    CompatEndpointKind,
    get_openai_compat_kind,
)

OPENAI = "openai"
OPENROUTER = "openrouter"
AUTOMATIC1111 = "automatic1111"
GEMINI = "gemini"
CUSTOM_HTTP = "custom_http"

PROVIDERS = {
    OPENAI: openai.generate,
    OPENROUTER: openrouter.generate,
    AUTOMATIC1111: automatic1111.generate,
    GEMINI: gemini.generate,
    CUSTOM_HTTP: custom_http.generate,
}


def detect_image_provider(endpoint):
    raw_endpoint = str(endpoint or "").strip()
    if not raw_endpoint:
        return OPENAI

    parsed = urlparse(raw_endpoint)
    hostname = (parsed.hostname or "").lower()
    path_parts = tuple(part for part in parsed.path.split("/") if part)
    endpoint_kind = get_openai_compat_kind(raw_endpoint)

    if endpoint_kind is CompatEndpointKind.OPENROUTER:
        return OPENROUTER

    if hostname == "generativelanguage.googleapis.com":
        return GEMINI

    if parsed.port == 7860 or path_parts[:2] == ("sdapi", "v1"):
        return AUTOMATIC1111

    return CUSTOM_HTTP
