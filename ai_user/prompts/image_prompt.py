import asyncio
import functools
from io import BytesIO
from typing import Callable, Coroutine, Optional

import pytesseract
import torch
from discord import Message
from PIL import Image
from transformers import (AutoTokenizer, VisionEncoderDecoderModel,
                          ViTImageProcessor)

from ai_user.prompts.base import Prompt
from ai_user.prompts.constants import MAX_MESSAGE_LENGTH


def to_thread(func: Callable) -> Coroutine:
    # https://stackoverflow.com/questions/65881761/discord-gateway-warning-shard-id-none-heartbeat-blocked-for-more-than-10-second
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


class ImagePrompt(Prompt):
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
            return None

        prompt = None
        scanned_text = await self._extract_text_from_image(image)
        if scanned_text and len(scanned_text.split()) > 10:
            prompt = [
                {"role": "system", "content": f"The following text is from a picture sent by user \"{self.message.author.name}\". {bot_prompt}"},
                {"role": "user", "content": scanned_text},
            ]
        else:
            confidence, caption = await self._create_prompt_from_image(image)
            if confidence > 0.45:
                prompt = [
                    {"role": "system", "content": f"The following is a description of a picture sent by user \"{self.message.author.name}\". {bot_prompt}"},
                    {"role": "user", "content": caption},
                ]
        if not prompt:
            return None
        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            prompt[:0] = [(self._format_message(self.message))]
        prompt[:0] = await self._get_previous_history()
        return prompt

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
    def _create_prompt_from_image(image: Image.Image):
        # based off https://huggingface.co/nlpconnect/vit-gpt2-image-captioning/discussions/6

        MODEL_NAME = "nlpconnect/vit-gpt2-image-captioning"
        max_length = 16  # max token length of the generated caption
        num_beams = 4  # choices to make at each step
        gen_kwargs = {"max_length": max_length,
                      "num_beams": num_beams,
                      "output_scores": True,
                      "return_dict_in_generate": True}

        model = VisionEncoderDecoderModel.from_pretrained(MODEL_NAME)
        feature_extractor = ViTImageProcessor.from_pretrained(MODEL_NAME)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        device = torch.device("cpu")
        model.to(device)

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
