from __future__ import annotations

import base64

import httpx

from aiuser.config.constants import GEMINI_IMAGE_MODEL


async def generate(description: str, request, endpoint: str | None = None) -> bytes:
    tokens = await request.bot.get_shared_api_tokens("gemini")
    api_key = tokens.get("apikey") or tokens.get("api_key")
    if not api_key:
        tokens = await request.bot.get_shared_api_tokens("openai")
        api_key = tokens.get("apikey") or tokens.get("api_key")
    if not api_key:
        raise ValueError(
            "Gemini API key not configured. Set with: [p]set api gemini apikey,<KEY>"
        )

    model = await request.config.guild(request.ctx.guild).function_calling_image_model()
    if not model and endpoint and "models/" in endpoint:
        seg = endpoint.split("models/", 1)[1].split(":", 1)[0].split("?", 1)[0]
        if seg:
            model = seg
    model = model or GEMINI_IMAGE_MODEL

    async with httpx.AsyncClient(timeout=240) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "x-goog-api-key": f"{api_key}",
                "Content-Type": "application/json",
            },
            json={"contents": [{"parts": [{"text": description}]}]},
        )
        resp.raise_for_status()
        data = resp.json()

    for cand in data.get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            inline = part.get("inline_data") or part.get("inlineData")
            b64 = inline and inline.get("data")
            if b64:
                return base64.b64decode(b64)
    raise ValueError("Gemini response contained no inline image data")
