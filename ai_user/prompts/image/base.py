import logging
from io import BytesIO
from discord import Message
from PIL import Image

from ai_user.prompts.base import Prompt
from ai_user.constants import MAX_MESSAGE_LENGTH
from ai_user.prompts.common.helpers import format_text_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class BaseImagePrompt(Prompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    async def _create_prompt(self, bot_prompt) -> MessagesList:
        image = self.message.attachments[0] if self.message.attachments else None

        if not image or not image.content_type.startswith('image/'):
            return None
        if image.size > await self.config.guild(self.message.guild).max_image_size():
            logger.info(f"Skipping large image in {self.message.guild.name}")
            return None

        image_bytes = BytesIO()
        await image.save(image_bytes)
        image_pillow = Image.open(image_bytes)
        messages = await self._process_image(image_pillow, bot_prompt)

        if not messages:
            return None

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            messages.add_msg(format_text_content(self.message), self.message)

        return messages

    async def _process_image(self, image: Image, bot_prompt: str) -> MessagesList:
        raise NotImplementedError(
            "_process_image() must be implemented in subclasses")

    @staticmethod
    def scale_image(image: Image, target_resolution: int) -> Image:
        width, height = image.size
        image_resolution = width * height
        if image_resolution > target_resolution:
            scale_factor = (target_resolution / image_resolution) ** 0.5
            return image.resize((int(width * scale_factor), int(height * scale_factor)), Image.Resampling.LANCZOS)
        return image
