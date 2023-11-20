import json
import logging
from io import BytesIO

from discord import Message
from PIL import Image

from aiuser.abc import MixinMeta
from aiuser.common.constants import IMAGE_RESOLUTION
from aiuser.common.enums import ScanImageMode
from aiuser.messages_list.converter.helpers import format_text_content
from aiuser.messages_list.converter.image.AI_horde import \
    process_image_ai_horde

logger = logging.getLogger("red.bz_cogs.aiuser")


async def transcribe_image(cog: MixinMeta, message: Message):
    config = cog.config
    attachment = message.attachments[0]

    buffer = BytesIO()
    await attachment.save(buffer)
    image = Image.open(buffer)
    image = scale_image(image, IMAGE_RESOLUTION ** 2)

    mode = ScanImageMode(await config.guild(message.guild).scan_images_mode())

    if mode == ScanImageMode.AI_HORDE:
        content = await process_image_ai_horde(cog, message, image)
    elif mode == ScanImageMode.LOCAL:
        try:
            from aiuser.messages_list.converter.image.local import \
                process_image_locally
            content = await process_image_locally(cog, message, image)
        except ImportError:
            logger.error("Local image scanning dependencies not installed, check cog README for instructions", exc_info=True)
            return None
    elif mode == ScanImageMode.LLM:
        content = [{"type": "image", "image_url": message.attachments[0].url}]
        if message.content != "":
            content.append({"type": "text", "text":  format_text_content(message)})

    if content:
        cog.cached_messages[message.id] = content

    return content


def scale_image(image: Image.Image, target_resolution: int) -> Image:
    width, height = image.size
    image_resolution = width * height
    if image_resolution > target_resolution:
        scale_factor = (target_resolution / image_resolution) ** 0.5
        return image.resize((int(width * scale_factor), int(height * scale_factor)), Image.Resampling.LANCZOS)
    return image
