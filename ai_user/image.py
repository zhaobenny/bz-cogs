import os
from io import BytesIO

import discord
import pytesseract
import torch
from PIL import Image
from transformers import (AutoTokenizer, VisionEncoderDecoderModel,
                          ViTImageProcessor)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

async def create_image_prompt(message : discord.Message):
        image = message.attachments[0]

        if not (image.content_type.startswith('image/')):
            return None

        image_bytes = await image.read()
        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

        if width > 1500 or height > 2000:  # do not process big images
            return None

        scanned = image2text(image)
        prompt = None

        if scanned and len(scanned.split()) > 10:
            prompt = [
                {"role": "system",
                    "content": f"The following text is from a picture sent by user \"{message.author.name}\". You are in a Discord text channel. Respond cynically in a short message to the image."},
                {"role": "user", "content": f"{scanned}"}
            ]
        else:
            confidence, caption = image2caption(image)
            if confidence > 0.45:
                prompt = [
                    {"role": "system",
                        "content": f"The following is a description of a picture sent by user \"{message.author.name}\". You are in a Discord text channel. Respond cynically in a short message to the image."},
                    {"role": "user", "content": f"{caption}"}
                ]

        return prompt


def image2text(image : Image.Image):
        result = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT, timeout=120)
        text = ""

        # Filter out words with low confidence scores
        for i, word in enumerate(result['text']):
            confidence = int(result['conf'][i])
            if confidence > 60:
                text = text + " " + word

        return text


def image2caption(image : Image.Image):
    model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    feature_extractor = ViTImageProcessor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
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

    pixel_values = feature_extractor(images=[image], return_tensors="pt").pixel_values
    pixel_values = pixel_values.to(device)

    output_ids = model.generate(pixel_values, **gen_kwargs)

    prob = float(torch.exp(output_ids.sequences_scores)[0])
    preds = tokenizer.batch_decode(output_ids.sequences, skip_special_tokens=True)
    pred = [pred.strip() for pred in preds][0]

    return prob, pred