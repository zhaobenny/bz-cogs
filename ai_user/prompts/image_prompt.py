import asyncio
import functools
from io import BytesIO
from typing import Optional, Callable, Coroutine

import pytesseract
import torch
from discord import Message, User
from PIL import Image
from transformers import (AutoTokenizer, VisionEncoderDecoderModel,
                          ViTImageProcessor)

from ai_user.prompts.constants import DEFAULT_IMAGE_PROMPT
from ai_user.prompts.base import Prompt

def to_thread(func: Callable) -> Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

class ImagePrompt(Prompt):
    def init(self, bot: User, message: Message, bot_prompt: str = None):
        super().init(bot, message, bot_prompt)

    def _get_default_bot_prompt(self) -> str:
        return DEFAULT_IMAGE_PROMPT

    async def _create_full_prompt(self) -> Optional[str]:
        image = self.message.attachments[0] if self.message.attachments else None

        if not image or not image.content_type.startswith('image/'):
            return None

        image_bytes = await image.read()
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

        if width > 1500 or height > 2000:
            return None

        prompt = None
        scanned_text = await self._extract_text_from_image(image)
        if scanned_text and len(scanned_text.split()) > 10:
            prompt = [
                {
                    "role": "system",
                    "content": f"The following text is from a picture sent by user \"{self.message.author.name}\". You are in a Discord text channel. {self.bot_prompt}"
                },
                {
                    "role": "user",
                    "content": scanned_text,
                },
            ]
        else:
            confidence, caption = await self._create_prompt_from_image(image)
            if confidence > 0.45:
                prompt = [
                    {
                        "role": "system",
                        "content": f"The following is a description of a picture sent by user \"{self.message.author.name}\". You are in a Discord text channel. {self.bot_prompt}"
                    },
                    {
                        "role": "user",
                        "content": caption,
                    },
                ]
        return prompt

    @to_thread
    def _extract_text_from_image(self, image: Image.Image):
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, timeout=30)
        text = " ".join(word for i, word in enumerate(data["text"])
                        if int(data["conf"][i]) >= 60)
        return text.strip()

    @to_thread
    def _create_prompt_from_image(self, image: Image.Image):
        model_name = "nlpconnect/vit-gpt2-image-captioning"
        model = VisionEncoderDecoderModel.from_pretrained(model_name)
        feature_extractor = ViTImageProcessor.from_pretrained(model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        device = torch.device("cpu")
        model.to(device)

        max_length = 16
        num_beams = 4
        gen_kwargs = {"max_length": max_length,
                    "num_beams": num_beams,
                    "output_scores": True,
                    "return_dict_in_generate": True}

        if image.mode != "RGB":
            image = image.convert(mode="RGB")

        pixel_values = feature_extractor(
            images=[image], return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(device)

        output_ids = model.generate(pixel_values, **gen_kwargs)

        prob = float(torch.exp(output_ids.sequences_scores)[0])
        preds = tokenizer.batch_decode(
            output_ids.sequences, skip_special_tokens=True)
        pred = preds[0].strip()


        return prob, pred