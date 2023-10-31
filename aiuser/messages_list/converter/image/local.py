import logging

import pytesseract
from discord import Message
from PIL import Image
from redbot.core.data_manager import cog_data_path
from transformers import BlipForConditionalGeneration, BlipProcessor

from aiuser.abc import MixinMeta
from aiuser.common.utilities import to_thread

logger = logging.getLogger("red.bz_cogs.aiuser")


async def process_image_locally(cog: MixinMeta, message: Message, image: Image.Image):
    path = cog_data_path(cog)
    scanned_text = await extract_text(image)
    author = message.author.nick or message.author.name

    if scanned_text and len(scanned_text.split()) > 10:
        content = f'User "{author}" sent: [Image saying "{scanned_text}"]'
    else:
        caption = await caption_image(image, path)
        content = f'User "{author}" sent: [Image: {caption}]'
    return content


@to_thread()
def caption_image(image: Image.Image, datapath):
    cache_path = datapath or "~/.cache/huggingface/datasets"
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base", cache_dir=cache_path)
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base", cache_dir=cache_path)

    inputs = processor(image, return_tensors="pt")

    out = model.generate(**inputs)

    caption = (processor.decode(out[0], skip_special_tokens=True))

    return caption


@to_thread()
def extract_text(image: Image.Image):
    data = pytesseract.image_to_data(
        image, output_type=pytesseract.Output.DICT, timeout=30)
    text = " ".join(word for i, word in enumerate(data["text"])
                    if int(data["conf"][i]) >= 60)
    return text.strip()
