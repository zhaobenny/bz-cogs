from aiuser.functions.imagerequest.providers import (
    automatic1111,
    custom_http,
    gemini,
    openai,
    openrouter,
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

def detect_provider(endpoint, client):
    """Return provider string only. Caller keeps original endpoint for generate()."""
    endpoint = str(endpoint or "").lower()
    if endpoint:
        if "openrouter.ai" in endpoint:
            return OPENROUTER
        if "generativelanguage.googleapis.com" in endpoint:
            return GEMINI
        if "/sdapi/v1" in endpoint or ":7860" in endpoint or "localhost:7860" in endpoint or "127.0.0.1:7860" in endpoint:
            return AUTOMATIC1111
        return CUSTOM_HTTP
    base_url = str(getattr(client, "base_url", "") or "").lower()
    if "openrouter.ai" in base_url:
        return OPENROUTER
    return OPENAI