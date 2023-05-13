import asyncio
import functools
import logging
from typing import Callable, Coroutine, Optional
from PIL import Image
from discord import Message
from redbot.core import Config

import pytesseract
from transformers import BlipForConditionalGeneration, BlipProcessor

from ai_user.common.constants import IMAGE_RESOLUTION
from ai_user.common.types import ContextOptions
from ai_user.prompts.common.messages_list import MessagesList
from ai_user.prompts.image.base import BaseImagePrompt

logger = logging.getLogger("red.bz_cogs.ai_user")


def to_thread(func: Callable) -> Coroutine:
    # https://stackoverflow.com/questions/65881761/discord-gateway-warning-shard-id-none-heartbeat-blocked-for-more-than-10-second
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


class LocalImagePrompt(BaseImagePrompt):
    def __init__(self, message: Message, config: Config, context_options: ContextOptions):
        super().__init__(message, config, context_options)

    async def _process_image(self, image: Image) -> Optional[MessagesList]:
        image = self.scale_image(image, IMAGE_RESOLUTION ** 2)
        scanned_text = await self._extract_text_from_image(image)

        if scanned_text and len(scanned_text.split()) > 10:
            caption_content = f'User "{self.message.author.name}" sent: [Image saying "{scanned_text}"]'
        else:
            caption = await self._create_caption_from_image(image)
            caption_content = f'User "{self.message.author.name}" sent: [Image: {caption}]'

        await self.messages.add_msg(caption_content, self.message)
        self.cached_messages[self.message.id] = caption_content
        return self.messages

    @staticmethod
    @to_thread
    def _extract_text_from_image(image: Image.Image):
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, timeout=30)
        text = " ".join(word for i, word in enumerate(data["text"])
                        if int(data["conf"][i]) >= 60)
        return text.strip()

    @staticmethod
    @to_thread
    def _create_caption_from_image(image: Image.Image):
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

        inputs = processor(image, return_tensors="pt")

        out = model.generate(**inputs)

        caption = (processor.decode(out[0], skip_special_tokens=True))

        return caption
