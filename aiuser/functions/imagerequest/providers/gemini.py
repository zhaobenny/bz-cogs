from __future__ import annotations

import base64

import httpx

from aiuser.config.constants import GEMINI_IMAGE_MODEL


async def generate(description: str, request, endpoint: str | None = None) -> bytes: 
    tokens = await request.bot.get_shared_api_tokens("gemini")
    api_key = tokens.get("apikey") or tokens.get("api_key")
    if not api_key:
        ot = await request.bot.get_shared_api_tokens("openai")
        api_key = ot.get("apikey") or ot.get("api_key")
    if not api_key:
        raise ValueError("Gemini API key not configured. Set with: [p]set api gemini apikey,<KEY>")

    model = endpoint or GEMINI_IMAGE_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": description}]}]}

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    for cand in data.get("candidates", []):
        content = cand.get("content") or {}
        for part in content.get("parts", []):
            inline = part.get("inline_data") or part.get("inlineData")
            if not inline:
                continue
            b64 = inline.get("data")
            if not b64:
                continue
            return base64.b64decode(b64)

    raise ValueError(
        "Gemini response contained no inline image data")

