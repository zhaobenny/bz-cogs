from io import BytesIO

import discord
import pytesseract
from PIL import Image


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
            caption = image2caption(image)

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
        pass
