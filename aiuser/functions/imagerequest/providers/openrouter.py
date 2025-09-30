import logging

from aiuser.config.constants import GEMINI_IMAGE_MODEL
from aiuser.functions.imagerequest.providers.util import fetch_image_bytes

logger = logging.getLogger("red.bz_cogs.aiuser")

async def generate(description, request, _):  
    model = await request.config.guild(request.ctx.guild).function_calling_image_model() or f"google/{GEMINI_IMAGE_MODEL}"
    r = await request.openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": description}],
        modalities=["image", "text"],
    )
    msg = r.choices[0].message
    for img in getattr(msg, "images", []) or []:
        iu = getattr(img, "image_url", None) or (img.get("image_url") if isinstance(img, dict) else None)
        if not iu:
            continue
        url = getattr(iu, "url", None) or (iu.get("url") if isinstance(iu, dict) else None)
        if url:
            return await fetch_image_bytes(url)
    raise ValueError("OpenRouter response contained no image data")
