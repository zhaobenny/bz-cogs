import logging
import re
from typing import Optional

from discord import Message, User

from ai_user.prompts.base import Prompt

logger = logging.getLogger("red.bz_cogs.ai_user")


class EmbedPrompt(Prompt):
    def __init__(self, bot: User, message: Message, bot_prompt: str = None):
        super().__init__(bot, message, bot_prompt)

    async def _create_full_prompt(self) -> Optional[str]:
        if len(self.message.embeds) == 0 or not self.message.embeds[0].title or not self.message.embeds[0].description:
            logger.debug(
                f"Skipping unloaded embed in {self.message.guild.name}")
            return None

        tenor_pattern = r"^https:\/\/tenor\.com\/view\/"

        is_tenor_gif = re.match(tenor_pattern, self.message.embeds[0].url)

        if is_tenor_gif:
            logger.debug(
                f"Skipping tenor gif: {self.message.embeds[0].url} in {self.message.guild.name}")
            return None

        prompt = []
        prompt.extend(await (self._get_previous_history()))
        prompt.extend([
            {"role": "system",
             "content": f"You are in a Discord text channel. A embed has been sent by {self.message.author.name}. {self.bot_prompt}"},
            {"role": "system",
             "content": f"The embed title is \"{self.message.embeds[0].title}\" and the description is \"{self.message.embeds[0].description}\""},
        ])

        if len(self.message.content) > 0:
            prompt.append(
                {"role": "user", "content": f"{self.message.content}"})

        return prompt
