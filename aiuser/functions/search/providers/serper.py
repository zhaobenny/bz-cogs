import json
import logging

import aiohttp

from aiuser.functions.context import ToolContext
from aiuser.functions.scrape.scrape import scrape_page
from aiuser.utils.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser.tools")

SERPER_ENDPOINT = "https://google.serper.dev/search"


async def search(query: str, tool_context: ToolContext) -> str:
    api_key = (await tool_context.services.bot.get_shared_api_tokens("serper")).get(
        "api_key"
    )
    if not api_key:
        return "Serper API key missing."
    return await SerperQuery(
        query, api_key, tool_context.ctx.guild.name
    ).execute_search()


class SerperQuery:
    def __init__(self, query: str, api_key: str, guild: str):
        self.api_key = api_key
        self.query = query
        self.guild = guild

    async def execute_search(self):
        payload = json.dumps({"q": self.query})
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(SERPER_ENDPOINT, data=payload) as response:
                    response.raise_for_status()

                    data = await response.json()
                    return await self.process_search_results(data)

        except Exception:
            logger.exception("Failed request to serper.io")
            return "An error occured while searching Google."

    async def process_search_results(self, data: dict):
        answer_box = data.get("answerBox")
        if answer_box and "snippet" in answer_box:
            return f"Use the following relevant information to generate your response: {answer_box['snippet']}"

        organic_results = [
            result
            for result in data.get("organic", [])
            if not contains_youtube_link(result.get("link", ""))
        ]
        if not organic_results:
            return "No relevant information was found using a Google search."

        first_result = organic_results[0]
        link = first_result.get("link")

        try:
            text_content = await scrape_page(
                link,
            )
            return f"Use the following relevant information to generate your response: {text_content}"

        except Exception:
            logger.debug(f"Failed scraping URL {link}", exc_info=True)
            knowledge_graph = data.get("knowledgeGraph", {})
            return f"Use the following relevant information to generate your response: {self.format_knowledge_graph(knowledge_graph) if knowledge_graph else first_result.get('snippet')}"

    def format_knowledge_graph(self, knowledge_graph: dict) -> str:
        title = knowledge_graph.get("title", "")
        type = knowledge_graph.get("type", "")
        description = knowledge_graph.get("description", "")
        text_content = f"{title} - ({type}) \n {description}"

        attributes = knowledge_graph.get("attributes", {})
        for attribute, value in attributes.items():
            text_content += f" \n {attribute}: {value}"

        return text_content
