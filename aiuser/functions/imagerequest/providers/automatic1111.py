from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from aiuser.response.llm_pipeline import LLMPipeline


async def generate(description: str, request: "LLMPipeline", endpoint: str) -> bytes:
    if not endpoint:
        raise ValueError("Automatic1111 provider requires an endpoint")
    endpoint = f"{endpoint.split('/sdapi/')[0].rstrip('/')}/sdapi/v1/txt2img"

    model = await request.config.guild(request.ctx.guild).function_calling_image_model()

    payload = {"prompt": description}
    if model:
        payload["override_settings"] = {"sd_model_checkpoint": model}

    async with httpx.AsyncClient(timeout=360) as c:
        r = await c.post(endpoint, json=payload)
        r.raise_for_status()
        data = r.json()
        
    imgs = data.get("images") or []
    if not imgs:
        raise ValueError("Automatic1111 response missing 'images'")
    b64 = imgs[0]
    return base64.b64decode(b64)
