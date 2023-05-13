import logging
from io import BytesIO
from typing import Optional
from discord import Message
from PIL import Image
from redbot.core import Config

from ai_user.common.constants import MAX_MESSAGE_LENGTH
from ai_user.common.types import ContextOptions
from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_text_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class BaseImagePrompt(Prompt):
    def __init__(self, message: Message, config: Config, context_options: ContextOptions):
        super().__init__(message, config, context_options)
        self.cached_messages = context_options.cached_messages

    async def _handle_message(self) -> Optional[MessagesList]:
        image = self.message.attachments[0] if self.message.attachments else None

        if not image or not image.content_type.startswith('image/'):
            return None
        if image.size > await self.config.guild(self.message.guild).max_image_size():
            logger.info(f"Skipping large image in {self.message.guild.name}")
            return None

        image_bytes = BytesIO()
        await image.save(image_bytes)
        image_pillow = Image.open(image_bytes)
        self.messages = await self._process_image(image_pillow)

        if not self.messages:
            return None

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            await self.messages.add_msg(format_text_content(self.message), self.message)

        return self.messages

    async def _process_image(self, image: Image) -> Optional[MessagesList]:
        raise NotImplementedError("_process_image() must be implemented in subclasses")

    @staticmethod
    def scale_image(image: Image, target_resolution: int) -> Image:
        width, height = image.size
        image_resolution = width * height
        if image_resolution > target_resolution:
            scale_factor = (target_resolution / image_resolution) ** 0.5
            return image.resize((int(width * scale_factor), int(height * scale_factor)), Image.Resampling.LANCZOS)
        return image
