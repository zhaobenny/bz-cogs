from __future__ import annotations

from typing import TYPE_CHECKING

from aiuser.functions.imagerequest.providers.util import fetch_image_bytes
from aiuser.llm.openai_compatible.client import setup_openai_client

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline


async def generate(description: str, request: "LLMPipeline", endpoint: str) -> bytes:
    model = (
        await request.config.guild(request.ctx.guild).function_calling_image_model()
        or "gpt-image-1"
    )
    client = await setup_openai_client(
        request.bot,
        request.config,
        base_url=endpoint,
    )
    if client is None:
        raise ValueError(
            "Image generation is unavailable because no OpenAI-compatible client could be created"
        )
    try:
        r = await client.images.generate(
            model=model,
            prompt=description,
            quality="standard",
            n=1,
            size="1024x1024",
            response_format="url",
        )
    finally:
        await client.close()
    return await fetch_image_bytes(r.data[0].url)
