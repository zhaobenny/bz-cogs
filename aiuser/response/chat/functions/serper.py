import json
import logging
import re

import aiohttp
import discord
from bs4 import BeautifulSoup

logger = logging.getLogger("red.bz_cogs.aiuser")


async def search_google(query, api_key: str = None, guild: discord.Guild = None):
    # serper.dev
    # [p]set api serper api_key,APIKEY
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
                return None

            first_result = data.get("organic", [])[0]
            link = first_result.get("link")

            text_content = await get_text_from_link(link)

            if text_content is None:
                knowledge_graph = data.get("knowledgeGraph", {})
                text_content = format_knowledge_graph(
                    knowledge_graph) if knowledge_graph else first_result.get("snippet")

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


async def get_text_from_link(link):
    headers = {
        "Cache-Control": "no-cache",
        "Referer": "https://www.google.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    logger.debug(f"Requesting {link}...")
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(link) as response:
            if response.status != 200:
                return None

            html_content = await response.text()

            text_content = find_best_text(html_content)

            if len(text_content) > 2000:
                text_content = text_content[:2000]

            text_content = "Use the following relevant infomation to generate your response: " + text_content

            return text_content


def find_best_text(html_content):
    def get_text_content(tag):
        return tag.get_text(separator=" ", strip=True) if tag else ""
    soup = BeautifulSoup(html_content, 'html.parser')

    bodycontent = soup.find('div', id='bodyContent')  # mainly for wikipedia
    if bodycontent:
        paragraph_tags = bodycontent.find_all('p')
        if not paragraph_tags:
            bodycontent_text = get_text_content(bodycontent)
        bodycontent_text = ' '.join(get_text_content(tag) for tag in paragraph_tags)
    else:
        bodycontent_text = ""

    article_tags = soup.find_all('article') or []
    main_tag = soup.find('main')
    article_text = max((get_text_content(tag) for tag in article_tags if tag and len(tag) > 100), default="")
    main_text = get_text_content(main_tag)

    if not any([article_text, main_text, bodycontent_text]) or all(len(text) < 100 for text in [article_text, main_text, bodycontent_text]):
        text_content = soup.get_text(separator=" ", strip=True)
    elif bodycontent_text:
        text_content = bodycontent_text
    else:
        text_content = max(article_text, main_text, key=len)

    return text_content
