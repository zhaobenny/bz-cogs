"""Search provider registry.

Adding a provider = write a module exposing
``async def search(query: str, tool_context: ToolContext) -> str``,
then register it in PROVIDERS here (plus PROVIDER_KEY_SERVICES if it
needs a shared API token).
"""

from aiuser.functions.search.providers import searxng, serper

SERPER = "serper"
SEARXNG = "searxng"

PROVIDERS = {
    SERPER: serper.search,
    SEARXNG: searxng.search,
}

# provider -> shared-API-token service name that must have an api_key set
PROVIDER_KEY_SERVICES = {
    SERPER: "serper",
}
