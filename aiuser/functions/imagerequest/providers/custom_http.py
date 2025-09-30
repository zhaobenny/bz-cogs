import base64

import httpx

from aiuser.functions.imagerequest.providers.util import fetch_image_bytes


async def generate(description, _, endpoint):
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(endpoint, json={"prompt": description})
        r.raise_for_status()
        data = r.json()
    url = data.get("image_url") or data.get("url")
    if url:
        return await fetch_image_bytes(url)
    b64 = data.get("image_base64") or data.get("image")
    if b64:
        if ":" in b64 and b64.split(":",1)[0].startswith("data"):
            b64 = b64.split(",",1)[-1]
        return base64.b64decode(b64)
    raise ValueError("Custom endpoint response missing image data")
