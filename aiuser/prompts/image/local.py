import asyncio
import functools
import logging
from typing import Callable, Coroutine, Optional

import pytesseract
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

from aiuser.common.constants import IMAGE_RESOLUTION
from aiuser.prompts.common.messages_list import MessagesList
from aiuser.prompts.image.base import BaseImagePrompt

logger = logging.getLogger("red.bz_cogs.aiuser")


def to_thread(func: Callable) -> Coroutine:
    # https://stackoverflow.com/questions/65881761/discord-gateway-warning-shard-id-none-heartbeat-blocked-for-more-than-10-second
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


class LocalImagePrompt(BaseImagePrompt):
    def __init__(self, *args,**kwargs):
        super().__init__(*args, **kwargs)

    async def _process_image(self, image: Image) -> Optional[MessagesList]:
        image = self.scale_image(image, IMAGE_RESOLUTION ** 2)
        scanned_text = await self._extract_text_from_image(image)
        author = self.message.author.nick or self.message.author.name

        if scanned_text and len(scanned_text.split()) > 10:
            caption_content = f'User "{author}" sent: [Image saying "{scanned_text}"]'
        else:
            caption = await self._create_caption_from_image(image)
            caption_content = f'User "{author}" sent: [Image: {caption}]'

        await self.messages.add_msg(caption_content, self.message, force=True)
        self.cached_messages[self.message.id] = caption_content
        return self.messages

    @to_thread
    def _create_caption_from_image(self, image: Image.Image):
        cache_path = self.cog_data_path or "~/.cache/huggingface/datasets"
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", cache_dir=cache_path)
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base", cache_dir=cache_path)

        inputs = processor(image, return_tensors="pt")

        out = model.generate(**inputs)

        caption = (processor.decode(out[0], skip_special_tokens=True))

        return caption

    @staticmethod
    @to_thread
    def _extract_text_from_image(image: Image.Image):
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, timeout=30)
        text = " ".join(word for i, word in enumerate(data["text"])
                        if int(data["conf"][i]) >= 60)
        return text.strip()
