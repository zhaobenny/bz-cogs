import logging

import aiohttp

from aiuser.utils.restricted_http import RestrictedHTTP

logger = logging.getLogger("red.bz_cogs.aiuser.tools")

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_TIMEOUT = aiohttp.ClientTimeout(total=70, connect=10)


async def firecrawl_scrape(link: str, tool_context, max_chars: int) -> str:
    logger.debug("Requesting %s to scrape with Firecrawl provider", link)
    RestrictedHTTP._require_url(link)

    tokens = await tool_context.services.bot.get_shared_api_tokens("firecrawl")
    api_key = tokens.get("api_key")
    if not api_key:
        return "Firecrawl api_key is not set."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": link,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "removeBase64Images": True,
    }

    async with aiohttp.ClientSession(
        headers=headers, timeout=FIRECRAWL_TIMEOUT
    ) as session:
        async with session.post(FIRECRAWL_SCRAPE_URL, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

    if not data.get("success", False):
        logger.debug("Firecrawl scrape failed for %s: %r", link, data)
        return "Firecrawl was unable to scrape the requested URL."

    scrape_data = data.get("data") or {}
    markdown = scrape_data.get("markdown") or ""
    if not markdown:
        logger.debug("Firecrawl returned no markdown for %s: %r", link, data)
        return "Firecrawl did not return readable markdown for the requested URL."

    res = f"Extracted Firecrawl markdown content:\n {markdown}"
    warning = scrape_data.get("warning")
    if warning:
        res = f"{res}\n\nFirecrawl warning:\n {warning}"

    if len(res) > max_chars:
        return res[:max_chars] + "...."
    return res
