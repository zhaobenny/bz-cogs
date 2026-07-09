from __future__ import annotations

import json
import logging

import aiohttp

from aiuser.functions.context import ToolContext
from aiuser.utils.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser.tools")

EXA_ENDPOINT = "https://api.exa.ai/search"
MAX_RESULTS = 100
TEXT_CHARACTER_LIMIT = 2000


async def search(query: str, tool_context: ToolContext) -> str:
    tokens = await tool_context.services.bot.get_shared_api_tokens("exa")
    api_key = tokens.get("api_key")
    if not api_key:
        return "Exa API key missing."

    results = await tool_context.services.config.guild(
        tool_context.ctx.guild
    ).function_calling_search_max_results()
    results = max(1, min(results or 1, MAX_RESULTS))

    payload = {
        "query": query,
        "type": "auto",
        "numResults": results,
        "contents": {
            "highlights": True,
            "text": {"maxCharacters": TEXT_CHARACTER_LIMIT},
        },
    }
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(EXA_ENDPOINT, json=payload) as response:
                logger.debug(
                    f'Requesting Exa search for "{query}" in '
                    f"{tool_context.ctx.guild.name}"
                )

                if response.status >= 400:
                    logger.debug(f"Exa response: {await response.text()}")
                response.raise_for_status()

                data = await response.json()
                return format_results(data, results)

    except Exception:
        logger.exception("Failed request to Exa")
        return "An error occured while searching."


def format_results(data: dict, max_results: int) -> str:
    results_json = []
    for result in data.get("results", []):
        url = result.get("url")
        if not isinstance(url, str):
            continue

        url = url.strip()
        if not url or contains_youtube_link(url):
            continue

        highlights = [
            highlight.strip()
            for highlight in result.get("highlights", [])
            if isinstance(highlight, str) and highlight.strip()
        ]
        text = result.get("text")
        content = "\n".join(highlights)
        if not content and isinstance(text, str):
            content = text.strip()
        if not content:
            continue

        formatted_result = {
            "title": result.get("title") or "",
            "url": url,
            "content": content,
        }
        published_date = result.get("publishedDate")
        if published_date:
            formatted_result["publishedDate"] = published_date

        results_json.append(formatted_result)
        if len(results_json) >= max_results:
            break

    if not results_json:
        return "No relevant information was found using an Exa search."

    return json.dumps(results_json)
