import json
import logging

import aiohttp
import discord
from bs4 import BeautifulSoup

from aiuser.common.utilities import contains_youtube_link

logger = logging.getLogger("red.bz_cogs.aiuser")


async def search_google(query, api_key: str = None, guild: discord.Guild = None):
    if not api_key:
        raise ValueError("No API key provided for serper.io")

    endpoint = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query,
    })

    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    logger.info(f"Searching Google using \"{query}\" with Serper.dev in {guild.name}")
    text_content = "No relevant information found on Google"

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(endpoint, data=payload) as response:
            data = await response.json()

            if response.status != 200:
                logger.warning(
                    f"Failed request to serper.io - {response.status}")
                return text_content

            answer_box = data.get("answerBox")
            if answer_box and "snippet" in answer_box:
                return "Use the following relevant infomation to generate your response: " + answer_box["snippet"]

            results = data.get("organic", [])

            results = [result for result in results if not contains_youtube_link(result.get("link", ""))]

            if not results:
                return text_content

            first_result = results[0]
            link = first_result.get("link")

            try:
                text_content = await scrape_page(link)
            except:
                logger.debug(f"Failed scraping url {link}", exc_info=1)
                knowledge_graph = data.get("knowledgeGraph", {})
                text_content = format_knowledge_graph(
                    knowledge_graph) if knowledge_graph else first_result.get("snippet")

    text_content = "Use the following relevant infomation to generate your response: " + text_content
    return text_content


def format_knowledge_graph(knowledge_graph):
    title = knowledge_graph.get("title", "")
    type = knowledge_graph.get("type", "")
    description = knowledge_graph.get("description", "")
    text_content = f"{title} - ({type}) \n {description}"

    attributes = knowledge_graph.get("attributes", {})
    for attribute, value in attributes.items():
        text_content += f" \n {attribute}: {value}"

    return text_content


async def scrape_page(link):
    headers = {
        "Cache-Control": "no-cache",
        "Referer": "https://www.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    logger.debug(f"Requesting {link} to scrape")
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(link) as response:
            if response.status != 200:
                response.raise_for_status()

            html_content = await response.text()

            text_content = find_best_text(html_content)

            if len(text_content) > 2000:
                text_content = text_content[:2000]

            return text_content


def find_best_text(html_content):
    def get_text_content(tag):
        return tag.get_text(separator=" ", strip=True) if tag else ""

    soup = BeautifulSoup(html_content, 'html.parser')

    paragraph_tags = soup.find_all('p') or []
    paragraph_text = ""
    for tag in paragraph_tags:
        tag_content = get_text_content(tag)
        paragraph_text = paragraph_text + tag_content if len(tag_content) > 100 else paragraph_text

    if not paragraph_text or len(paragraph_text) < 300:
        text_content = soup.get_text(separator=" ", strip=True)
    else:
        text_content = paragraph_text

    return text_content
