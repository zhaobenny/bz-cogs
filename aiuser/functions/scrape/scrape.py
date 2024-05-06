import logging
import aiohttp
from bs4 import BeautifulSoup

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
            html_content = await response.text()
            text_content = find_best_text(html_content)

            if len(text_content) > 2000:
                text_content = text_content[:2000]

            return text_content


def find_best_text(html_content: str):
    def get_text_content(tag):
        return tag.get_text(separator=" ", strip=True) if tag else ""

    soup = BeautifulSoup(html_content, 'html.parser')
    paragraph_tags = soup.find_all('p') or []

    paragraph_text = " ".join([get_text_content(tag) for tag in paragraph_tags if len(get_text_content(tag)) > 100])

    if not paragraph_text or len(paragraph_text) < 300:
        return soup.get_text(separator=" ", strip=True)

    return paragraph_text
