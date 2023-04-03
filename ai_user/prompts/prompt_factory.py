import importlib
import logging
import re

from ai_user.prompts.embed_prompt import EmbedPrompt
from ai_user.prompts.text_prompt import TextPrompt

logger = logging.getLogger("red.bz_cogs.ai_user")

try:
    logger.debug("Attempting to load pytesseract...")
    importlib.import_module("pytesseract")
    logger.debug("Attempting to load torch...")
    importlib.import_module("torch")
    logger.debug("Attempting to load transformers...")
    importlib.import_module("transformers")
    from ai_user.prompts.image_prompt import ImagePrompt
    logger.debug("Loaded all image processing dependencies...")
except:
    from ai_user.prompts.dummy_image_prompt import ImagePrompt
    logger.warning("No image processing dependencies installed / supported.")


async def create_prompt_instance(message, config):
    url_pattern = re.compile(r"(https?://\S+)")
    contains_url = url_pattern.search(message.content)
    if message.attachments and await config.scan_images():
        return ImagePrompt(message, config)
    elif contains_url:
        return EmbedPrompt(message, config)
    else:
        return TextPrompt(message, config)

