from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiuser.config.constants import GEMINI_IMAGE_MODEL, OPENROUTER_API_V1_URL
from aiuser.functions.imagerequest.providers.util import fetch_image_bytes
from aiuser.llm.openai_compatible.client import setup_openai_client

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline

logger = logging.getLogger("red.bz_cogs.aiuser.tools")


async def generate(description: str, request: "LLMPipeline", _: str) -> bytes:
    model = (
        await request.config.guild(request.ctx.guild).function_calling_image_model()
        or f"google/{GEMINI_IMAGE_MODEL}"
    )
    client = await setup_openai_client(
        request.bot,
        request.config,
        base_url=OPENROUTER_API_V1_URL,
    )
    if client is None:
        raise ValueError(
            "Image generation is unavailable because no OpenRouter client could be created"
        )
    try:
        r = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": description}],
            modalities=["image", "text"],
        )
    finally:
        await client.close()
    msg = r.choices[0].message
    for img in getattr(msg, "images", []) or []:
        iu = getattr(img, "image_url", None) or (
            img.get("image_url") if isinstance(img, dict) else None
        )
        if not iu:
            continue
        url = getattr(iu, "url", None) or (
            iu.get("url") if isinstance(iu, dict) else None
        )
        if url:
            return await fetch_image_bytes(url)
    raise ValueError("OpenRouter response contained no image data")
