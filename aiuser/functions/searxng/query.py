import json
import logging

import aiohttp
import ssl
from redbot.core import commands
import unicodedata
from trafilatura import extract

from aiuser.utils.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser")

SEARXNG_ENDPOINT = "https://search.collective.lan/search"
MAX_RESULTS = 5
WORDS_LIMIT = 5000


async def search_searxng(query: str, ctx: commands.Context):
    return await SearXNGQuery(query, ctx).execute_search()


class SearXNGQuery:
    def __init__(self, query: str, ctx: commands.Context):
        self.query = query
        self.guild = ctx.guild.name

    async def execute_search(self):
        params = {}
        params["q"] = self.query
        params["format"] = "json"
        payload = json.dumps({"q": self.query, "format": "json"})
        headers = {'Content-Type': 'application/json'}
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(SEARXNG_ENDPOINT, params=params, ssl=ssl_context) as response:
                    response.raise_for_status()
                    logger.info(f"Requesting {response.real_url} from search query \"{self.query}\" in {self.guild}")

                    if response.content_type != "application/json":
                        logger.info(f"Reponse: {await response.text()}")
                        return "An error occured while searching."
                    else:
                        data = await response.json()
                        return await self.process_search_results(data)

        except Exception:
            logger.exception("Failed request to SearXNG")
            return "An error occured while searching."

    async def process_search_results(self, data: dict):
        """Return data to the LLM."""

        results_json = []
        for result in data["results"]:
            title_site = self.remove_emojis(result["title"])
            url_site = result["url"]
            snippet = result.get("content", "")

            try:
                response_site = await self.scrape_page(url_site)
                truncated_content = self.truncate_to_n_words(
                    response_site, WORDS_LIMIT
                )

                results_json.append({
                    "title": title_site,
                    "url": url_site,
                    "content": truncated_content,
                    "snippet": self.remove_emojis(snippet),
                })

            except Exception as e:
                return None

        return results_json[:MAX_RESULTS]


    def remove_emojis(self, text):
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))
    
    def truncate_to_n_words(self, text, token_limit):
        tokens = text.split()
        truncated_tokens = tokens[:token_limit]
        return " ".join(truncated_tokens)    
    
    async def scrape_page(self, link: str):
        headers = {
            "Cache-Control": "no-cache",
            "Referer": "https://www.google.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

        logger.info(f"Requesting {link} from search query \"{self.query}\" in {self.guild}")
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(link) as response:
                response.raise_for_status()
                html_content = await response.text()
                text_content = extract(html_content)

                if len(text_content) > 5000:
                    text_content = text_content[:5000] + "..."

                return text_content    