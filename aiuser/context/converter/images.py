import base64
import logging
from io import BytesIO
from typing import Any, Dict, List

from discord import Message
from PIL import Image
from redbot.core import Config

from aiuser.context.converter.formatters import format_text_content

logger = logging.getLogger("red.bz_cogs.aiuser.context")


async def format_image(config: Config, message: Message) -> List[Dict[str, Any]]:
    attachment = message.attachments[0]

    buffer = BytesIO()
    await attachment.save(buffer)
    image = Image.open(buffer)
    max_size = await config.guild(message.guild).max_image_size()
    image = scale_image(image, max_size)

    content: List[Dict[str, Any]] = []
    if message.content != "":
        content.append({"type": "text", "text": format_text_content(message)})

    fp = BytesIO()
    image.save(fp, "PNG")
    fp.seek(0)
    base64_image = base64.b64encode(fp.read()).decode()
    content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
        }
    )
    return content


def scale_image(image: Image.Image, target_resolution: int) -> Image.Image:
    width, height = image.size
    image_resolution = width * height
    if image_resolution > target_resolution:
        scale_factor = (target_resolution / image_resolution) ** 0.5
        return image.resize(
            (int(width * scale_factor), int(height * scale_factor)),
            Image.Resampling.LANCZOS,
        )
    return image
