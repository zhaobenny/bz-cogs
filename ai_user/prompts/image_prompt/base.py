import logging
from io import BytesIO
from typing import Optional

from discord import Message
from PIL import Image

from ai_user.prompts.base import Prompt
from ai_user.prompts.constants import MAX_MESSAGE_LENGTH

logger = logging.getLogger("red.bz_cogs.ai_user")


class BaseImagePrompt(Prompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    async def _create_prompt(self, bot_prompt) -> Optional[list[dict[str, str]]]:
        image = self.message.attachments[0] if self.message.attachments else None

        if not image or not image.content_type.startswith('image/'):
            return None

        image_bytes = await image.read()
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

        if width > 1500 or height > 2000:
            logger.info(f"Skipping large image in {self.message.guild.name}")
            return None

        prompt = await self._process_image(image, bot_prompt)

        if not prompt:
            return None

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            prompt[:0] = [(self._format_message(self.message))]

        prompt[:0] = await self._get_previous_history()
        return prompt

    async def _process_image(self, image : Image, bot_prompt: str) -> Optional[list[dict[str, str]]]:
        raise NotImplementedError(
            "_process_image() must be implemented in subclasses")
