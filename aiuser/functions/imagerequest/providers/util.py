import base64

import httpx


async def fetch_image_bytes(source: str) -> bytes:
    """Fetch image bytes from a URL, data URI, or raw base64 string.

    Args:
        source: http(s) URL like https://..., a data URI (data:image/png;base64,...),
            or a raw base64-encoded string.
    Returns:
        Raw image bytes.
    Raises:
        ValueError: if the source format is unsupported or base64 decode fails.
        httpx.HTTPError: if HTTP request fails.
    """
    if source.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(source)
            r.raise_for_status()
            return r.content
    if source.startswith("data:"):
        _, _, b64 = source.partition(",")
        return base64.b64decode(b64)
    return base64.b64decode(source, validate=True)
