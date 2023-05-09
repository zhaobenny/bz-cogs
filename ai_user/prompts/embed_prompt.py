import logging
import re
from typing import Optional

from discord import Message

from ai_user.prompts.base import Prompt
from ai_user.constants import MAX_MESSAGE_LENGTH

logger = logging.getLogger("red.bz_cogs.ai_user")


class EmbedPrompt(Prompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    async def _create_prompt(self, bot_prompt) -> Optional[list[dict[str, str]]]:
        if len(self.message.embeds) == 0 or not self.message.embeds[0].title or not self.message.embeds[0].description:
            logger.debug(
                f"Skipping unloaded / unsupported embed in {self.message.guild.name}")
            return None

        prompt = []
        prompt.extend(await (self._get_previous_history()))
        prompt.extend([
            {"role": "system",
             "content": f"A embed has been sent by {self.message.author.name}. {bot_prompt}"},
            {"role": "system",
             "content": f"The embed title is \"{self.message.embeds[0].title}\" and the description is \"{self.message.embeds[0].description}\""},
        ])

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            prompt[:0] = [self._format_message(self.message)]

        return prompt
