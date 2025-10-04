import base64
import logging
from io import BytesIO

from discord import Message
from PIL import Image

from aiuser.context.converter.helpers import format_text_content
from aiuser.types.abc import MixinMeta

logger = logging.getLogger("red.bz_cogs.aiuser")


async def transcribe_image(cog: MixinMeta, message: Message):
    attachment = message.attachments[0]

    buffer = BytesIO()
    await attachment.save(buffer)
    image = Image.open(buffer)
    max_size = await cog.config.guild(message.guild).max_image_size()
    image = scale_image(image, max_size)

    content = []
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


def scale_image(image: Image.Image, target_resolution: int) -> Image:
    width, height = image.size
    image_resolution = width * height
    if image_resolution > target_resolution:
        scale_factor = (target_resolution / image_resolution) ** 0.5
        return image.resize(
            (int(width * scale_factor), int(height * scale_factor)),
            Image.Resampling.LANCZOS,
        )
    return image