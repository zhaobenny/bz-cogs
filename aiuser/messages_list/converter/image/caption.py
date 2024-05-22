
import base64
import logging
from io import BytesIO

from discord import Message
from PIL import Image

from aiuser.abc import MixinMeta
from aiuser.common.enums import ScanImageMode
from aiuser.messages_list.converter.helpers import format_text_content
from aiuser.messages_list.converter.image.AI_horde import \
    process_image_ai_horde

logger = logging.getLogger("red.bz_cogs.aiuser")


async def transcribe_image(cog: MixinMeta, message: Message):
    config = cog.config
    attachment = message.attachments[0]
    mode = ScanImageMode(await config.guild(message.guild).scan_images_mode())

    buffer = BytesIO()
    await attachment.save(buffer)
    image = Image.open(buffer)
    maxsize = 2048*2048 if mode == ScanImageMode.LLM else 1024*1024
    image = scale_image(image, maxsize)

    content = await process_image(cog, message, image, mode)

    if content and mode != ScanImageMode.LLM:
        cog.cached_messages[message.id] = content

    return content


async def process_image(cog: MixinMeta, message: Message, image: Image, mode: ScanImageMode):
    if mode == ScanImageMode.AI_HORDE:
        return await process_image_ai_horde(cog, message, image)
    elif mode == ScanImageMode.LOCAL:
        try:
            from aiuser.messages_list.converter.image.local import \
                process_image_locally
            return await process_image_locally(cog, message, image)
        except ImportError:
            logger.exception("Local image scanning dependencies not installed, check cog README for instructions")
            return None
    elif mode == ScanImageMode.LLM:
        content = []
        if message.content != "":
            content.append({"type": "text", "text": format_text_content(message)})
        fp = BytesIO()
        image.save(fp, "PNG")
        fp.seek(0)
        content.append(
            {"type": "image_url", "image_url": {
             "url": f"data:image/png;base64,{base64.b64encode(fp.read()).decode()}"}
             })
        return content
    else:
        return None


def scale_image(image: Image.Image, target_resolution: int) -> Image:
    width, height = image.size
    image_resolution = width * height
    if image_resolution > target_resolution:
        scale_factor = (target_resolution / image_resolution) ** 0.5
        return image.resize((int(width * scale_factor), int(height * scale_factor)), Image.Resampling.LANCZOS)
    return image
