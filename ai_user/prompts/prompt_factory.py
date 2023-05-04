import logging
import re

from ai_user.prompts.embed_prompt import EmbedPrompt
from ai_user.prompts.text_prompt import TextPrompt

logger = logging.getLogger("red.bz_cogs.ai_user")


async def create_prompt_instance(message, config):
    url_pattern = re.compile(r"(https?://\S+)")
    contains_url = url_pattern.search(message.content)
    if message.attachments and await config.guild(message.guild).scan_images():
        try:
            from ai_user.prompts.image_prompt import ImagePrompt
            return ImagePrompt(message, config)
        except ImportError:
            logger.error(
                f"Unable load image scanning dependencies, disabling image scanning for this server f{message.guild.name}...")
            await config.guild(message.guild).scan_images.set(False)
            raise
    elif contains_url:
        return EmbedPrompt(message, config)
    else:
        return TextPrompt(message, config)
