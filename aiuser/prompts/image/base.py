import logging
from io import BytesIO
from typing import Optional
from PIL import Image

from aiuser.common.constants import MAX_MESSAGE_LENGTH
from aiuser.prompts.base import Prompt
from aiuser.prompts.common.helpers import format_text_content
from aiuser.prompts.common.messagethread import MessageThread

logger = logging.getLogger("red.bz_cogs.aiuser")


class BaseImagePrompt(Prompt):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _handle_message(self) -> Optional[MessageThread]:
        image = self.message.attachments[0] if self.message.attachments else None

        if not image or not image.content_type.startswith('image/'):
            return None
        if image.size > await self.config.guild(self.message.guild).max_image_size():
            logger.info(f"Skipping large image in {self.message.guild.name}")
            return None

        image_bytes = BytesIO()
        await image.save(image_bytes)
        image_pillow = Image.open(image_bytes)

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            await self.messages.add_msg(format_text_content(self.message), self.message)

        self.messages = await self._process_image(image_pillow)

        if not self.messages:
            return None

        return self.messages

    async def _process_image(self, image: Image) -> Optional[MessageThread]:
        raise NotImplementedError("_process_image() must be implemented in subclasses")

    @staticmethod
    def scale_image(image: Image, target_resolution: int) -> Image:
        width, height = image.size
        image_resolution = width * height
        if image_resolution > target_resolution:
            scale_factor = (target_resolution / image_resolution) ** 0.5
            return image.resize((int(width * scale_factor), int(height * scale_factor)), Image.Resampling.LANCZOS)
        return image
