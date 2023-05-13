import logging
import re

from discord import Message
from redbot.core import Config

from ai_user.common.constants import MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH
from ai_user.common.types import ContextOptions
from ai_user.prompts.base import Prompt
from ai_user.prompts.common.helpers import format_text_content
from ai_user.prompts.common.messages_list import MessagesList

logger = logging.getLogger("red.bz_cogs.ai_user")


class TextPrompt(Prompt):
    def __init__(self, message: Message, config: Config, context_options: ContextOptions):
        super().__init__(message, config, context_options)

    def _is_acceptable_message(self, message: Message) -> bool:
        mention_pattern = re.compile(r'^<@!?(\d+)>$')

        if not message.content:
            logger.debug(f"Skipping empty message in {message.guild.name}")
            return False

        if mention_pattern.match(message.content):
            logger.debug(f"Skipping singular mention message in {message.guild.name}")
            return False

        if len(message.content) < MIN_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping short message: {message.content} in {message.guild.name}")
            return False

        if len(message.content.split()) > MAX_MESSAGE_LENGTH:
            logger.debug(
                f"Skipping long message: {message.content} in {message.guild.name}")
            return False

        return True

    async def _handle_message(self) -> MessagesList:
        if not self._is_acceptable_message(self.message):
            return None

        await self.messages.add_msg(format_text_content(self.message), self.message)

        return self.messages
