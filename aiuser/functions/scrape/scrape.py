import logging

import aiohttp
from trafilatura import extract

logger = logging.getLogger("red.bz_cogs.aiuser")


async def scrape_page(link: str):
    headers = {
        "Cache-Control": "no-cache",
        "Referer": "https://www.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(link) as response:
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '').lower()
            if not 'text/html' in content_type:
                raise ValueError("Content type is not text/html")

            html_content = await response.text()
            res = "Link content: " + extract(html_content)

            if len(res) > 5000:
                res = res[:5000] + "..."

            return res
