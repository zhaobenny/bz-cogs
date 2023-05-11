import logging
from typing import Optional

from discord import Message

from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_embed_content
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

        messages = MessagesList(self.bot, self.config, self.message)

        await messages.add_system(f"{bot_prompt}")

        await messages.add_msg(format_embed_content(self.message), self.message)

        await messages.create_context(self.message, self.start_time)

        return messages
