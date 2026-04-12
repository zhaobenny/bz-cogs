import logging

import aiohttp
import ssl
import unicodedata
from redbot.core import commands

from aiuser.functions.scrape.scrape import scrape_page
from aiuser.utils.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser.tools")

WORDS_LIMIT = 5000


async def search_searxng(
    query: str, endpoint: str, results: int, ctx: commands.Context
):
    if not endpoint:
        return "SearXNG endpoint missing."
    return await SearXNGQuery(query, endpoint, results, ctx).execute_search()


class SearXNGQuery:
    def __init__(self, query: str, endpoint: str, results: int, ctx: commands.Context):
        self.query = query
        self.guild = ctx.guild.name
        self.endpoint = endpoint
        self.results = results

    async def execute_search(self):
        params = {}
        params["q"] = self.query
        params["format"] = "json"
        headers = {"Content-Type": "application/json"}
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    self.endpoint, params=params, ssl=ssl_context
                ) as response:
                    response.raise_for_status()
                    logger.debug(
                        f'Requesting {response.real_url} from search query "{self.query}" in {self.guild}'
                    )

                    if response.content_type != "application/json":
                        logger.debug(f"Reponse: {await response.text()}")
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
        x = 0
        for result in data["results"]:
            if contains_youtube_link(result["url"]):
                continue
            if x >= self.results:
                break
            title_site = self.remove_emojis(result["title"])
            url_site = result["url"]
            snippet = result.get("content", "")

            try:
                response_site = await scrape_page(
                    url_site,
                )
                truncated_content = self.truncate_to_n_words(response_site, WORDS_LIMIT)

                results_json.append(
                    {
                        "title": title_site,
                        "url": url_site,
                        "content": truncated_content,
                        "snippet": self.remove_emojis(snippet),
                    }
                )
                x += 1

            except Exception:
                continue

        if not results_json:
            return "No relevant information was found using a SearXNG search."

        import json

        return json.dumps(results_json[: self.results])

    def remove_emojis(self, text):
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))

    def truncate_to_n_words(self, text, token_limit):
        tokens = text.split()
        truncated_tokens = tokens[:token_limit]
        return " ".join(truncated_tokens)
