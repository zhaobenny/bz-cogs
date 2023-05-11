import logging
import re
from typing import Optional

from discord import Message
from ai_user.constants import MAX_MESSAGE_LENGTH

from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_text_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class EmbedPrompt(Prompt):
    def __init__(self, message: Message, config, start_time):
        super().__init__(message, config, start_time)

    async def _create_prompt(self, bot_prompt) -> Optional[list[dict[str, str]]]:
        if len(self.message.embeds) == 0 or not self.message.embeds[0].title or not self.message.embeds[0].description:
            logger.debug(
                f"Skipping unloaded / unsupported embed in {self.message.guild.name}")
            return None

        messages = MessagesList(self.bot, self.config)

        if self.message.content and not len(self.message.content.split(" ")) > MAX_MESSAGE_LENGTH:
            messages.add_msg(format_text_content(self.message), self.message)

        messages.add_system(f"You are {self.bot.name}. A embed has been sent by {self.message.author.name}. {bot_prompt}")

        messages.add_msg(f" \"{self.message.embeds[0].title}\" \"{self.message.embeds[0].description}\"", self.message)

        await messages.create_context(self.message, self.start_time)

        return messages
