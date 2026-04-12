import logging

from trafilatura import extract

from aiuser.utils.restricted_http import RestrictedHTTP

logger = logging.getLogger("red.bz_cogs.aiuser.tools")
MAX_SCRAPED_CHARS = 5000


def _truncate_scraped_content(text: str, *, max_chars: int) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + "...."
    return text


async def scrape_page(
    link: str,
    *,
    max_chars: int = MAX_SCRAPED_CHARS,
):
    logger.info("Requesting %s to scrape", link)

    async with RestrictedHTTP.session() as session:
        async with session.get(link) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                html_content = await RestrictedHTTP.text(response)
                extracted = extract(html_content) or ""
                res = f"Extracted HTML content:\n {extracted}"
            else:
                logger.debug("Non-HTML content type: %s", content_type)
                raw = await RestrictedHTTP.read(response)
                text_preview = raw.decode("utf-8", errors="replace")
                res = f"Content-Type:\n {content_type}. Extracted content:\n {text_preview}"

            return _truncate_scraped_content(res, max_chars=max_chars)
