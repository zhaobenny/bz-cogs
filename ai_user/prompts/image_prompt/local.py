import asyncio
import functools
import logging
from typing import Callable, Coroutine, Optional

import pytesseract
import torch
from discord import Message
from PIL import Image
from transformers import (AutoTokenizer, VisionEncoderDecoderModel,
                          ViTImageProcessor)

from ai_user.prompts.image_prompt.base import BaseImagePrompt

logger = logging.getLogger("red.bz_cogs.ai_user")

def to_thread(func: Callable) -> Coroutine:
    # https://stackoverflow.com/questions/65881761/discord-gateway-warning-shard-id-none-heartbeat-blocked-for-more-than-10-second
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper


class LocalImagePrompt(BaseImagePrompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    async def _process_image(self, image : Image, bot_prompt: str) -> Optional[list[dict[str, str]]]:
        prompt = None
        scanned_text = await self._extract_text_from_image(image)
        if scanned_text and len(scanned_text.split()) > 10:
            prompt = [
                {"role": "system", "content": f"The following text is from a picture sent by user \"{self.message.author.name}\". {bot_prompt}"},
                {"role": "user", "content": scanned_text},
            ]
        else:
            confidence, caption = await self._create_caption_from_image(image)
            if confidence > 0.45:
                prompt = [
                    {"role": "system", "content": f"Pretend you can see the following image. The following is a description of a picture sent by user \"{self.message.author.name}\". {bot_prompt}"},
                    {"role": "user", "content": caption},
                ]
        if prompt == None:
            logger.info(f"Skipping image in {self.message.guild.name}. Low confidence in image caption and text recognition.")
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
    def _create_caption_from_image(image: Image.Image):
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
