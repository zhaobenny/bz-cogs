"""Scrape provider registry."""

from typing import Awaitable, Callable

from aiuser.functions.context import ToolContext
from aiuser.functions.scrape.providers import firecrawl, local

LOCAL = "local"
FIRECRAWL = "firecrawl"
MAX_SCRAPED_CHARS = 12000
ScrapeProvider = Callable[[str, ToolContext, int], Awaitable[str]]

PROVIDERS = {
    LOCAL: local.local_scrape,
    FIRECRAWL: firecrawl.firecrawl_scrape,
}


async def configured_scrape_provider(tool_context: ToolContext) -> ScrapeProvider:
    provider = await tool_context.services.config.guild(
        tool_context.ctx.guild
    ).function_calling_scrape_provider()
    provider = (provider or LOCAL).strip().lower()
    return PROVIDERS.get(provider) or PROVIDERS[LOCAL]
