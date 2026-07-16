import base64
import logging
from io import BytesIO
from typing import Any, Dict, List

from discord import Attachment, Message
from PIL import Image
from redbot.core import Config

from aiuser.context.converter.formatters import format_text_content

logger = logging.getLogger("red.bz_cogs.aiuser.context")


async def format_image(
    config: Config, message: Message, attachments: List[Attachment]
) -> List[Dict[str, Any]]:
    max_size = await config.guild(message.guild).max_image_size()
    detail = await config.guild(message.guild).scan_images_detail()

    content: List[Dict[str, Any]] = []
    if message.content != "":
        content.append({"type": "text", "text": format_text_content(message)})

    for attachment in attachments:
        buffer = BytesIO()
        await attachment.save(buffer)
        image = Image.open(buffer)
        image = scale_image(image, max_size)

        fp = BytesIO()
        image.save(fp, "PNG")
        fp.seek(0)
        base64_image = base64.b64encode(fp.read()).decode()
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": detail,
                },
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
