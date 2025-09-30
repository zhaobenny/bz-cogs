import base64

import httpx


async def generate(description, _, endpoint):
    endpoint = f"{endpoint.split('/sdapi/')[0].rstrip('/')}/sdapi/v1/txt2img"
    async with httpx.AsyncClient(timeout=240) as c:
        r = await c.post(endpoint, json={"prompt": description})
        r.raise_for_status()
        data = r.json()
    imgs = data.get("images") or []
    if not imgs:
        raise ValueError("Automatic1111 response missing 'images'")
    b64 = imgs[0]
    return base64.b64decode(b64)
