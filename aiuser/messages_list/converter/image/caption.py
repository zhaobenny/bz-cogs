import logging
from io import BytesIO

from discord import Message
from PIL import Image

from aiuser.abc import MixinMeta
from aiuser.common.constants import AI_HORDE_MODE, IMAGE_RESOLUTION, LOCAL_MODE
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

    mode = await config.guild(message.guild).scan_images_mode()

    if mode == AI_HORDE_MODE:
        content = await process_image_ai_horde(cog, message, image)
    elif mode == LOCAL_MODE:
        try:
            from aiuser.messages_list.converter.image.local import \
                process_image_locally
            content = await process_image_locally(cog, message, image)
        except ImportError:
            logger.error("Local image scanning dependencies not installed, check cog README for instructions", exc_info=True)
            return None

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
