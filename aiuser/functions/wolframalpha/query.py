import logging
import xml.etree.ElementTree as ET

import aiohttp
from redbot.core import commands

logger = logging.getLogger("red.bz_cogs.aiuser")


async def ask_wolfram_alpha(query: str, app_id: str, ctx: commands.Context):
    # Credit to: https://github.com/hollowstrawberry/crab-cogs/blob/b113287f89c9045d387a75edf9de21b9a2dab08a/gptmemory/function_calling.py

    url = "http://api.wolframalpha.com/v2/query?"
    payload = {"input": query, "appid": app_id}
    headers = {"user-agent": "Red-cog/2.0.0"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, params=payload) as response:
                response.raise_for_status()
                result = await response.text()
    except Exception:
        logger.exception("Asking Wolfram Alpha")
        return "An error occured while asking Wolfram Alpha."

    root = ET.fromstring(result)
    plaintext = []
    for pt in root.findall(".//plaintext"):
        if pt.text:
            plaintext.append(pt.text.capitalize())
    if not plaintext:
        return "Wolfram Alpha is unable to answer the question. Try to answer with your own knowledge."
    # lines after the 3rd are often irrelevant in answers such as currency conversion
    content = "\n".join(plaintext[:3])

    if len(content) > 2000:
        content = content[:2000-3] + "..."

    return f"[Wolfram Alpha] [Question: {query}] [Answer:] {content}"
