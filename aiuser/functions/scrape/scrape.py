import logging

import aiohttp
from trafilatura import extract

logger = logging.getLogger("red.bz_cogs.aiuser")


async def scrape_page(link: str):
    headers = {
        "Cache-Control": "no-cache",
        "Referer": "https://www.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(link) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                html_content = await response.text()
                extracted = extract(html_content) or ""
                res = "Link content: " + extracted
            else:
                logger.debug("Non-HTML content type: %s", content_type)
                raw = await response.read()
                text_preview = raw.decode("utf-8", errors="replace")
                res = f"Content-Type: {content_type}). Content: " + text_preview

            if len(res) > 5000:
                res = res[:5000] + "..."

            return res
